import asyncio
import logging
import sys
from dotenv import load_dotenv
from os import getenv
import json
import random
import os
from threading import Thread
import time

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ForceReply


load_dotenv()
TOKEN = getenv("tg_token")

data = {}
sessions = {}
bot = None
captcha_answer = None
auth_answer = None

dp = Dispatcher()

@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Use /login to log in duhhh")


@dp.message(Command("login"))
async def command_start_handler(message: Message, command: CommandObject) -> None:
    if command.args is None:
        await message.answer("Use \n/login _login_ _password_\nso I can steal your cookies and report you to the government")
        return
    if str(message.from_user.id) not in data:
        data[str(message.from_user.id)] = {}
    data[str(message.from_user.id)]["vk_login"] = command.args.split(" ", maxsplit=1)[0]
    data[str(message.from_user.id)]["vk_password"] = command.args.split(" ", maxsplit=1)[1]
    json.dump(data,open("data.json","w"))
    Thread(target=login_and_start_longpoll,args=[str(message.from_user.id)]).start() 
    await message.answer("You System32 was deleted lmao\nNow you can use /link to link a vk chat with a telegram chat")

@dp.message(Command("link"))
async def command_start_handler(message: Message, command: CommandObject) -> None:
    if command.args is None:
        await message.answer("get chat id and use\n/link _id_\nI can already read all your messages, so don't worry about your privacy")
        return
    if str(message.from_user.id) not in data:
        data[str(message.from_user.id)] = {}
    if "chats" not in data[str(message.from_user.id)]:
        data[str(message.from_user.id)]["chats"] = {}
    data[str(message.from_user.id)]["chats"][str(message.chat.id)] = command.args
    json.dump(data,open("data.json","w"))
    await message.answer("Linked successfully")

@dp.message(F.reply_to_message)
async def reply_handler(message: Message):
    global captcha_answer, auth_answer
    if message.reply_to_message.text.startswith("Бля ты походу бот, реши капчу:"):
        captcha_answer = message.text
    elif message.reply_to_message.text.startswith("Напиши код двухфакторной аутентификации в ответе на это сообщение."):
        auth_answer = message.text

@dp.message()
async def message_handler(message: Message) -> None:
    if str(message.from_user.id) not in data:
        await message.answer("Not logged in! use /login")
        return
    if "chats" not in data[str(message.from_user.id)]:
        await message.answer("Chat not linked! Use /link")
        return
    if str(message.chat.id) not in data[str(message.from_user.id)]["chats"]:
        await message.answer("Chat not linked! Use /link")
        return
    api = sessions[str(message.from_user.id)].get_api()
    api.messages.send(peer_id=data[str(message.from_user.id)]["chats"][str(message.chat.id)], message=message.text, random_id=random.randint(-2**31, 2**31 - 1),v="5.199")


def captcha_handler(captcha,user_id):
    global captcha_answer
    asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=user_id, reply_markup=ForceReply(selective=True), text=f"Бля ты походу бот, реши капчу: {captcha.get_url()}\Решение напиши в ответе на это сообщение"), loop)
    while(captcha_answer == None):
        time.sleep(1)
    print("Got captcha solution!")
    key = captcha_answer
    captcha_answer = None
    return captcha.try_again(key)

def auth_handler(user_id):
    global auth_answer
    asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=user_id, reply_markup=ForceReply(selective=True), text=f"Напиши код двухфакторной аутентификации в ответе на это сообщение. Возможно тебе говорили не передавать коды другим людям, но я не человек, мне коды кидать можно)"), loop)
    while(auth_answer == None):
        time.sleep(1)
    print("Got auth code!")
    key = auth_answer
    auth_answer = None
    return key, True

def login_and_start_longpoll(userid):
    sessions[userid] = vk_api.VkApi(data[userid]["vk_login"], data[userid]["vk_password"], captcha_handler=lambda captcha:captcha_handler(captcha,userid), auth_handler=lambda:auth_handler(userid), scope=4096, app_id=2685278)
    sessions[userid].auth()
    longpoll(sessions[userid])

def longpoll(vk_session: vk_api.VkApi):
    print(vk_session)
    longpoll = VkLongPoll(vk_session)

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW:
            print('Новое сообщение ', end='')

            if event.from_me:
                print('от меня для ', end='')
            elif event.to_me:
                print('для меня от ', end='')
            if event.from_user:
                print(event.user_id, end='')
            elif event.from_chat:
                print(event.user_id, 'в беседе', event.chat_id, end='')
            elif event.from_group:
                print('группы', event.group_id, end='')
            print(', текст: ', event.text)

            if event.to_me:
                for uid in data:
                    for chat in data[uid]["chats"]:
                        if data[uid]["chats"][chat]==str(2000000000+int(event.chat_id)):
                            users_get_result = vk_session.get_api().users.get(user_ids=event.user_id)[0]
                            name = f'[{users_get_result["first_name"]} {users_get_result["last_name"]}](https://vk.com/id{event.user_id})\n'
                            text = name+""+event.text
                            asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=chat, text=text), loop)
                            

async def main() -> None:
    global data, sessions, bot, loop
    if os.path.isfile("data.json"):
        data = json.load(open("data.json"))
        for user in data:
            Thread(target=login_and_start_longpoll,args=[str(user)]).start() 

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    loop = asyncio.get_event_loop()
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())