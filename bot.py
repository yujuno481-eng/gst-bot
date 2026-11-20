
import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import random
import aiohttp

# =========================
# BASIC SETTINGS
# =========================

TOKEN = "MTU2OTY2MDkzMjQxMjQxMTk0NA.G01Pon.f6OzxfJWoCuE_11jGTynuuqU2IWtL0XH2IFimE"
GUILD_ID = 1568951322751930438

KST = timezone(timedelta(hours=9))

OLLAMA_URL = "http://localhost:11434/api/chat"
AI_MODEL = "qwen3.5:4b"

MAX_HISTORY = 8
conversation_history = {}


SYSTEM_PROMPT = """
너는 동굴 해병대 성장도움단의 공식 AI 안내 봇이다.

[말투]
- 친절하고 자연스러운 한국어를 사용한다.
- 일상 대화에서는 친근하게 대화한다.
- 필요한 경우 적절한 이모지를 사용한다.
- 질문에 맞는 답변을 직접 제공한다.

[역할]
- 동굴 해병대 성장도움단 관련 안내를 제공한다.
- 배움신청 방법을 물어보면 /배움신청 명령어를 안내한다.
- 배움신청은 성장도움단의 배움신청 채널에서 진행한다고 설명한다.
- 일반 상식, 일상 대화, 기술 질문에도 성실하게 답변한다.

[중요]
- 사용자가 자기소개를 요청하지 않았다면 자기소개를 하지 않는다.
- 모든 질문에 똑같은 인사말이나 소개 문구를 반복하지 않는다.
- 질문의 핵심을 파악하고 바로 답변한다.
- 이전 대화의 맥락을 참고한다.
- 모르는 서버 정보는 추측하지 않는다.
- 실제로 실행하지 않은 작업을 완료했다고 말하지 않는다.
- 답변은 기본적으로 간결하게 작성한다.
"""


# =========================
# BOT CLASS
# =========================

class GSTBot(commands.Bot):

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=180)
        )

    async def close(self):
        if hasattr(self, "http_session"):
            if not self.http_session.closed:
                await self.http_session.close()

        await super().close()


intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = GSTBot(
    command_prefix="!",
    intents=intents
)

guild = discord.Object(id=GUILD_ID)


# =========================
# AI RESPONSE
# =========================

async def ask_ai(user_id, channel_id, guild_id, user_message):

    key = (guild_id, channel_id, user_id)

    if key not in conversation_history:
        conversation_history[key] = []

    history = conversation_history[key]

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    messages.extend(history)

    messages.append({
        "role": "user",
        "content": user_message
    })

    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "stream": False,

        # Thinking 비활성화
        "think": False,

        # 모델을 30분 동안 메모리에 유지
        "keep_alive": "30m",

        # 응답 속도 및 길이 조절
        "options": {
            "num_ctx": 2048,
            "num_predict": 180,
            "temperature": 0.7
        }
    }

    async with bot.http_session.post(
        OLLAMA_URL,
        json=payload
    ) as response:

        if response.status != 200:
            error_text = await response.text()
            raise Exception(
                f"Ollama API 오류 ({response.status}): {error_text}"
            )

        data = await response.json()

    answer = data.get("message", {}).get("content", "").strip()

    if not answer:
        answer = "답변을 생성하지 못했어요. 다시 질문해 주세요!"

    # 대화 기록 저장
    history.append({
        "role": "user",
        "content": user_message
    })

    history.append({
        "role": "assistant",
        "content": answer
    })

    conversation_history[key] = history[-MAX_HISTORY:]

    return answer


# =========================
# BOT START
# =========================

@bot.event
async def on_ready():

    try:
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()

        synced = await bot.tree.sync(guild=guild)

        print("========================")
        print(f"BOT ONLINE: {bot.user}")
        print(f"GUILD COMMAND SYNC: {len(synced)}")
        print(f"AI MODEL: {AI_MODEL}")
        print("AI THINKING: OFF")
        print("========================")

    except Exception as e:
        print(f"SYNC ERROR: {e}")


# =========================
# BOT TALK + AI
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    try:

        if bot.user and bot.user in message.mentions:

            content = message.content

            content = content.replace(
                f"<@{bot.user.id}>", ""
            )

            content = content.replace(
                f"<@!{bot.user.id}>", ""
            )

            content = content.strip()

            if not content:
                content = "안녕하세요!"

            try:

                async with message.channel.typing():

                    answer = await ask_ai(
                        user_id=message.author.id,
                        channel_id=message.channel.id,
                        guild_id=message.guild.id if message.guild else 0,
                        user_message=content
                    )

                chunks = [
                    answer[i:i + 1900]
                    for i in range(0, len(answer), 1900)
                ]

                for index, chunk in enumerate(chunks):

                    if index == 0:
                        await message.reply(
                            chunk,
                            allowed_mentions=discord.AllowedMentions.none()
                        )
                    else:
                        await message.channel.send(
                            chunk,
                            allowed_mentions=discord.AllowedMentions.none()
                        )

            except Exception as e:

                print(f"AI ERROR: {e}")

                await message.reply(
                    "죄송합니다. 현재 AI 연결에 문제가 발생했어요. 😥\n"
                    "잠시 후 다시 시도해 주세요!",
                    allowed_mentions=discord.AllowedMentions.none()
                )

    finally:
        await bot.process_commands(message)


# =========================
# LEARNING APPLICATION
# =========================

@bot.tree.command(
    name="배움신청",
    description="배움 신청을 접수합니다.",
    guild=guild
)
async def 배움신청(interaction: discord.Interaction):

    channel = interaction.channel

    if (
        not isinstance(channel, discord.TextChannel)
        or channel.name != "배움신청"
        or channel.category is None
        or channel.category.name != "성장도움단ㅣGrowth Support Team"
    ):
        await interaction.response.send_message(
            "이 명령어는 성장도움단 배움신청 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )
        return

    server = interaction.guild

    if server is None:
        await interaction.response.send_message(
            "서버에서만 사용할 수 있습니다.",
            ephemeral=True
        )
        return

    target_roles = ["성장도움단", "성장도움관"]

    candidates = [
        member
        for member in server.members
        if not member.bot
        and member.status == discord.Status.online
        and any(role.name in target_roles for role in member.roles)
    ]

    selected = random.choice(candidates) if candidates else None

    now = datetime.now(KST)

    weekdays = [
        "월요일", "화요일", "수요일",
        "목요일", "금요일", "토요일", "일요일"
    ]

    time_text = now.strftime("%Y년 %m월 %d일 ")
    time_text += weekdays[now.weekday()]
    time_text += now.strftime(" %p %I:%M")
    time_text = time_text.replace("AM", "오전").replace("PM", "오후")

    embed = discord.Embed(
        title="📖 배움 신청이 접수되었습니다",
        description=(
            "아래 내용을 확인하고 스레드 및 배움실에서 "
            "일정을 조율하세요.\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="👤 신청자 (배움 대상)",
        value=interaction.user.mention,
        inline=False
    )

    embed.add_field(
        name="🏫 배정된 성장도움관",
        value=selected.mention if selected else "현재 온라인 담당자가 없습니다.",
        inline=False
    )

    embed.add_field(
        name="🚪 배정된 배움실",
        value="미지정",
        inline=False
    )

    embed.add_field(
        name="📖 배움 카테고리",
        value="`📖 기본 배움`",
        inline=False
    )

    embed.add_field(
        name="🖼️ 첨부 증거",
        value="`사진 0장`",
        inline=False
    )

    embed.add_field(
        name="📅 신청 시각",
        value=time_text,
        inline=False
    )

    embed.add_field(
        name="📝 신청 사유",
        value="ㅣ",
        inline=False
    )

    embed.set_footer(
        text="동굴 해병대 성장도움단 도움 시스템"
    )

    await interaction.response.send_message(
        embed=embed,
        allowed_mentions=discord.AllowedMentions(
            users=True,
            roles=False,
            everyone=False
        )
    )


# =========================
# ERROR HANDLING
# =========================

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"EVENT ERROR: {event}")


# =========================
# RUN BOT
# =========================

bot.run(TOKEN)
