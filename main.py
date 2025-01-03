import asyncio

from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from pkg.platform.types import Plain, MessageChain
import os
import json
import time
from datetime import datetime
import requests
import re
# 注册插件
@register(name="ShowMeNav", description="基金净值查询助手", version="0.1", author="exneverbur")
class MyPlugin(BasePlugin):
    # 指定的时间列表，格式为 'HH:MM' 的字符串
    specified_times = ['10:00', '12:00', '14:00', '14:50']
    file_path = "show_me_nav.json"
    check_daily = 55

    # 插件加载时触发
    def __init__(self, host: APIHost):
        # 解析json文件 保存到self.file中
        self.read_or_create_json()
        # 创建定时器 每分钟检查 整点报时


    # 异步初始化
    async def initialize(self):
        pass

    # 当收到群消息时触发
    @handler(GroupNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        receive_text = ctx.event.text_message
        cleaned_text = re.sub(r'@\S+\s*', '', receive_text).strip()
        if cleaned_text.startswith('$'):  # 检查是否为命令
            parts = cleaned_text.split(' ', 1)  # 分割命令和参数
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ''
            group_id = ctx.event.launcher_id
            print("接收指令:",command, "参数：", args)
            print("len(parts)", len(parts))
            if command == "$订阅":
                if len(parts) <= 1:
                    print("请输入要关注的基金代号")
                    ctx.add_return("reply", ["请输入要关注的基金代号"])
                else:
                    self.apply(group_id, args)
                    ctx.add_return("reply", ["订阅成功"])
            elif command == "$查询":
                if len(parts) <= 1:
                    print("请输入要查询的基金代号")
                    ctx.add_return("reply", ["请输入要查询的基金代号"])
                else:
                    data = self.request(args)
                    res = f"[{data['fundcode']}]{data['name']} 当前涨幅: {data['gszzl']}({data['gztime']})"
                    ctx.add_return("reply", [res])
            elif command == "$开启播报":
                if hasattr(self, 'run_task') and not self.run_task.done():
                    await ctx.reply(["订阅任务已经开始执行了~"])
                    return
                try:
                    self.run_task = asyncio.create_task(self.run(ctx))
                    await ctx.reply(["订阅任务开始执行"])
                except Exception as e:
                    self.ap.logger.error(f"创建订阅任务失败: {e}")

        # 阻止该事件默认行为（向接口获取回复）
        ctx.prevent_default()


    # 插件卸载时触发
    def __del__(self):
        pass

    # 读取json配置
    def read_or_create_json(self):
        # 检查文件是否存在
        print("基金助手初始化")
        if not os.path.exists(self.file_path):
            # 创建一个空的字典作为JSON文件的基础结构
            data = {
                "group_ids": []
            }

            # 将空字典写入到新的JSON文件中
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"{self.file_path} 已创建.")

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.file = json.load(f)
        except json.JSONDecodeError:
            self.ap.logger.error("【基金净值助手】json文件解析失败")
            print("【基金净值助手】json文件解析失败")

    # 写入json文件
    def write_json(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.file, f, indent=4)

    # 判断当前时间并发送请求
    def check_time(self):
        # 获取当前时间并格式化为 'HH:MM'
        current_time = datetime.now().strftime('%H:%M')

        # 如果当前时间与指定时间列表中的任何一个时间匹配，则发送请求
        if current_time in self.specified_times:
            return True
        return False

    def request(self, fCode: str):
        api_url = f'https://fundgz.1234567.com.cn/js/{fCode}.js?rt={time.time_ns()}'
        try:
            response = requests.get(api_url)
            response.raise_for_status()  # 检查请求是否成功

            # 解析JSONP格式的响应内容
            content = response.text
            start_index = content.find('{')
            end_index = content.rfind('}') + 1
            print(content)
            if start_index != -1 and end_index != 0:
                json_str = content[start_index:end_index]  # 提取出JSON部分
                print(json_str)
                data = json.loads(json_str)  # 将JSON字符串转换为Python字典
                return data  # 返回解析后的数据以便进一步使用
            else:
                print(f"无法解析{fCode}的响应内容")
                self.remove_fCode(fCode)
                return None
        except requests.exceptions.RequestException as e:
            print(f"API 请求失败: {e}")
            return None

    def remove_fCode(self, fCode: str):
        # 遍历self.file中的组ID以找到并移除fCode
        group_ids = self.file.get("group_ids", [])
        for group_id in group_ids:
            codes = self.file.get(str(group_id), [])
            if fCode in codes:
                codes.remove(fCode)
                print(f"fCode {fCode} 已从组 {group_id} 中移除")
                break
        else:
            print(f"fCode {fCode} 未找到")

    def apply(self, group_id: int, fCode: str):
        data = self.file
        # 确保 'group_ids' 键存在并是一个列表
        if 'group_ids' not in data:
            data['group_ids'] = []

        # 如果提供的 group_id 不在 'group_ids' 列表中，则添加进去
        if group_id not in data['group_ids']:
            data['group_ids'].append(group_id)

        # 检查给定的 group_id 是否已经作为键存在于数据中
        if str(group_id) not in data:
            # 如果不存在，则创建一个新的键，并初始化为包含 fCode 的列表
            data[str(group_id)] = [fCode]
        else:
            # 如果存在，则检查是否需要添加新的 fCode
            if fCode not in data[str(group_id)]:
                data[str(group_id)].append(fCode)
            # 如果 fCode 已经存在，则什么都不做
        self.write_json()

    async def run(self, ctx:EventContext):
        while True:
            isTime = self.check_time()
            if isTime:
                msg = ['你的基金净值播报员来啦！']
                for group_id in self.file['group_ids']:
                    for fCode in self.file[str(group_id)]:
                        data = self.request(fCode)
                        msg.append(f"[\n{data['fundcode']}]{data['name']} 当前涨幅: {data['gszzl']}({data['gztime']})")
                    if len(msg) > 0:
                        await ctx.send_message("group", group_id, MessageChain(msg))
            await asyncio.sleep(self.check_daily)