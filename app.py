from flask import Flask, request, abort
import os
from linebot.v3.webhook import WebhookHandler  
from linebot.v3.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage  # TextMessageContentは削除
import openai
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
)

# Flaskのインスタンス作成
app = Flask(__name__)

# 環境変数の取得
openai_api_key = os.environ.get("OPENAI_API_KEY")
channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
channel_secret = os.environ.get("LINE_CHANNEL_SECRET")

# 環境変数が設定されているか確認
if not all([openai_api_key, channel_access_token, channel_secret]):
    raise ValueError("環境変数の設定が不十分です。")

# OpenAIクライアントの設定
client = openai.OpenAI(api_key=openai_api_key)

# LINE Botの設定
configuration = Configuration(access_token=channel_access_token)
with ApiClient(configuration) as api_client:
    line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(channel_secret)

@app.route("/")
def hello_world():
    return "hello world!"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        abort(400, description="Signature missing")

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400, description="Invalid signature error")
    except Exception:
        abort(500, description="Internal server error")

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        # LINEからのメッセージを取得
        user_message = event.message.text

        # ChatGPTに送信して返答を取得
        messages = [{"role": "user", "content": user_message}]
        response = client.chat.completions.create(
            model="gpt-4-turbo", messages=messages
        )

        # ChatGPTからの返答を取得
        chatgpt_response = response.choices[0].message.content

        # ChatGPTからの返答をLINEに送信
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessageContent(text=chatgpt_response)]
                )
            )

    except openai.error.OpenAIError as e:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessageContent(text="現在サービスに接続できません。しばらくしてから再度お試しください。")]
                )
            )
    except Exception:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessageContent(text="エラーが発生しました。")]
                )
            )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
