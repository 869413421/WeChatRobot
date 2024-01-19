#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import sys
import traceback
from datetime import datetime
from hashlib import md5

import httpx
import openai
import requests
from openai import OpenAI

from openapi import openapi

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from configuration import Config


class ChatGPT:

    def __init__(self, conf: dict) -> None:
        client = OpenAI(
            api_key=conf["key"],
            base_url=conf["api"],
            http_client=httpx.Client(
                proxies=conf["proxy"],
            ),
        )
        self.openapi = openapi.OpenAPIHandler()
        self.client = client
        self.conversation_list = {}
        self.system_content_msg = {"role": "system", "content": conf["prompt"]}

    def __repr__(self):
        return 'ChatGPT'

    @staticmethod
    def value_check(conf: dict) -> bool:
        if conf:
            if conf.get("key") and conf.get("api") and conf.get("prompt"):
                return True
        return False

    def get_answer(self, question: str, wxid: str) -> str:
        # wxid或者roomid,个人时为微信id，群消息时为群id
        self.updateMessage(wxid, question, "user")
        try:

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "weather",
                        "description": "获取中国城市天气预报",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {
                                    "type": "string",
                                    "description": "城市名称",
                                },
                            },
                            "required": ["city"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "search_movie",
                        "description": "搜索影视资源,返回电影资源标题和网盘链接",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "movie_name": {
                                    "type": "string",
                                    "description": "影视名称",
                                },
                            },
                            "required": ["movie_name"],
                        },
                    },
                }
            ]
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo-1106",
                messages=self.conversation_list[wxid],
                tools=tools,
                tool_choice="auto",
            )
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            # Step 2: check if the model wanted to call a function
            if tool_calls:
                # Step 3: call the function
                # Note: the JSON response may not always be valid; be sure to handle errors
                available_functions = {
                    "weather": self.openapi.weather,
                    "search_movie": self.openapi.search_movie,
                }  # only one function in this example, but you can have multiple
                self.conversation_list[wxid].append(response_message)  # extend conversation with assistant's reply
                # Step 4: send the info for each function call and function response to the model

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions[function_name]
                    function_args = json.loads(tool_call.function.arguments)
                    if function_name == "weather":
                        function_response = function_to_call(
                            city=function_args.get("city"),
                        )
                    elif function_name == "search_movie":
                        function_response = function_to_call(
                            movie_name=function_args.get("movie_name"),
                        )
                        function_response = function_response['data'][:3]

                    self.conversation_list[wxid].append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(function_response),
                        }
                    )  # extend conversation with function response
                second_response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo-1106",
                    messages=self.conversation_list[wxid],
                )  # get a new response from the model where it can see the function response
                print(second_response)
                rsp = second_response.choices[0].message.content
                rsp = rsp[2:] if rsp.startswith("\n\n") else rsp
                rsp = rsp.replace("\n\n", "\n")
            else:
                rsp = response_message.content
                rsp = rsp[2:] if rsp.startswith("\n\n") else rsp
                rsp = rsp.replace("\n\n", "\n")

            self.updateMessage(wxid, rsp, "assistant")
        except openai.AuthenticationError as e3:
            rsp = "OpenAI API 认证失败，请检查 API 密钥是否正确"
        except openai.APIConnectionError as e2:
            rsp = "无法连接到 OpenAI API，请检查网络连接"
        except openai.APIError as e1:
            rsp = "OpenAI API 返回了错误：" + str(e1)
        except Exception as e0:
            # 打印堆栈
            print(traceback.print_exc())
            rsp = "发生未知错误：" + str(e0)

        return rsp

    def generateAudio(self, question: str) -> str:
        """生成语音"""
        response = self.client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=question
        )
        today = datetime.now().strftime("%Y-%m-%d")
        dirPath = os.path.join(os.path.join(os.getcwd(), "audio"), today)
        if not os.path.exists(dirPath):
            os.makedirs(dirPath)
        fileName = md5(question.encode()).hexdigest() + ".mp3"
        savePath = os.path.join(dirPath, fileName)
        response.stream_to_file(savePath)
        return savePath

    def generateImage(self, question: str) -> str:
        """生成图片"""
        try:
            response = self.client.images.generate(
                model="dall-e-2",
                prompt=question,
                size="512x512",
                # size="1024x1024",
                n=1,
                # style="vivid"
            )

            image_url = response.data[0].url
            today = datetime.now().strftime("%Y-%m-%d")
            dirPath = os.path.join(os.path.join(os.getcwd(), "images"), today)
            if not os.path.exists(dirPath):
                os.makedirs(dirPath)
            fileName = md5(question.encode()).hexdigest() + ".jpg"
            savePath = os.path.join(dirPath, fileName)

            response = requests.get(image_url)
            if response.status_code == 200:
                with open(savePath, 'wb') as file:
                    file.write(response.content)
                return savePath
            else:
                return ""
        except Exception as e:
            print(e)
            return ""

    def updateMessage(self, wxid: str, question: str, role: str) -> None:
        now_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        time_mk = "当需要回答时间时请直接参考回复:"
        # 初始化聊天记录,组装系统信息
        if wxid not in self.conversation_list.keys():
            question_ = [
                self.system_content_msg,
                {"role": "system", "content": "" + time_mk + now_time}
            ]
            self.conversation_list[wxid] = question_

        # 当前问题
        content_question_ = {"role": role, "content": question}
        self.conversation_list[wxid].append(content_question_)

        for cont in self.conversation_list[wxid]:
            # 判断是否是字典
            if not isinstance(cont, dict):
                continue
            if cont["role"] != "system":
                continue
            if cont["content"].startswith(time_mk):
                cont["content"] = time_mk + now_time

        # 只存储10条记录，超过滚动清除
        i = len(self.conversation_list[wxid])
        if i > 50:
            print("滚动清除微信记录：" + wxid)
            # 删除多余的记录，倒着删，且跳过第一个的系统消息
            del self.conversation_list[wxid][1]


if __name__ == "__main__":

    config = Config().CHATGPT
    if not config:
        exit(0)

    chat = ChatGPT(config)
    res = chat.generateImage("一个被逼入绝境的女侠，面对一群强大的敌人，面色凝重，眼神坚定，手中的长剑紧紧握住，准备迎接最后的战斗。")
    while True:
        q = input(">>> ")
        try:
            time_start = datetime.now()  # 记录开始时间
            print(chat.get_answer(q, "wxid"))
            time_end = datetime.now()  # 记录结束时间

            print(f"{round((time_end - time_start).total_seconds(), 2)}s")  # 计算的时间差为程序的执行时间，单位为秒/s
        except Exception as e:
            print(e)
