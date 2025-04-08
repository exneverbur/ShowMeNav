import asyncio

from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from pkg.platform.types.message import Plain, MessageChain, Image
import os
import json
import time
from datetime import datetime
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# 注册插件
@register(name="ShowMeNav", description="基金净值查询小助手+自动播报员!", version="1.1", author="exneverbur")
class MyPlugin(BasePlugin):
    # 指定的时间列表，格式为 'HH:MM' 的字符串
    specified_times = ['10:00', '12:00', '14:00', '14:50']
    # 订阅列表的保存路径
    file_path = "show_me_nav.json"
    # 每隔多少秒检查一次时间
    check_daily = 30

    # 云图爬取相关配置
    # 是否开启云图下载功能
    need_yuntu = True
    # 云图下载位置(发送完成后会自动删除图片)
    download_dir = os.path.join('plugins', 'ShowMeNav', 'temp')
    # chrome driver的路径 driver必须与你自己的谷歌浏览器的版本对应
    # 可以在此网站下载 https://registry.npmmirror.com/binary.html?path=chrome-for-testing/
    chrome_driver_path = "C:/Users/lifen/Desktop/langbot/chromedriver-win64/chromedriver.exe"
    target_url = "https://dapanyuntu.com/"

    # 插件加载时触发
    def __init__(self, host: APIHost):
        # 解析json文件 保存到self.file中
        self.read_or_create_json()
        # 创建定时器 每分钟检查 整点报时
        print(f"[基金播报助手]已创建定时任务, 当前接受消息的群号: {self.file.get('group_ids', [])}")

        self.run_task = asyncio.create_task(self.run())


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
                    self.run_task = asyncio.create_task(self.run())
                    await ctx.reply(["订阅任务开始执行"])
                except Exception as e:
                    self.ap.logger.error(f"创建订阅任务失败: {e}")
            elif command == "$推送基金":
                await self.push_nav_message(group_id)
            # 阻止该事件默认行为（向接口获取回复）
            ctx.prevent_postorder()


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

    async def run(self):
        while True:
            is_time = self.check_time()
            if is_time:
                await self.push_nav_message()

            await asyncio.sleep(self.check_daily)

    async def push_nav_message(self, target_group_id=None):
        yuntu_path = None
        if self.need_yuntu:
            yuntu_path = await self.download_yuntu()
        try:
            msg = ['你的基金净值播报员来啦！']
            # 下载云图
            for group_id in self.file['group_ids']:
                if target_group_id is not None and group_id != target_group_id:
                    continue
                for fCode in self.file[str(group_id)]:
                    data = self.request(fCode)
                    msg.append(f"\n[{data['fundcode']}]{data['name']} 当前涨幅: {data['gszzl']}({data['gztime']})")
                try:
                    if len(msg) > 1:
                        await self.host.send_active_message(
                            adapter=self.host.get_platform_adapters()[0],
                            target_type="group",
                            target_id=group_id,
                            message=MessageChain(msg)
                        )
                    if self.need_yuntu and yuntu_path is not None:
                        await self.host.send_active_message(
                            adapter=self.host.get_platform_adapters()[0],
                            target_type="group",
                            target_id=group_id,
                            message=MessageChain([Image(path=yuntu_path)]),
                        )
                except Exception as e:
                    print("推送基金消息时出错:", e)
        finally:
            if yuntu_path is not None:
                os.remove(yuntu_path)


    # 下载云图
    async def download_yuntu(self):
        # 配置 Chrome 选项
        chrome_options = webdriver.ChromeOptions()
        # 启用无头模式
        chrome_options.add_argument("--headless")
        # 指定下载路径
        absolute_path = os.path.abspath(self.download_dir)
        prefs = {
            "download.default_directory": absolute_path,  # 设置默认下载路径
            "download.prompt_for_download": False,  # 禁用下载提示
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        # 初始化 WebDriver
        service = Service(self.chrome_driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        try:
            # 打开目标网页
            driver.get(self.target_url)
            time.sleep(3)  # 根据实际情况调整等待时间以确保页面加载完毕

            wait = WebDriverWait(driver, 20)  # 最长等待 20 秒
            capture_button = wait.until(EC.element_to_be_clickable((By.ID, "capture")))
            capture_button.click()
            time.sleep(3)
            print("开始下载图片, 等待图片下载完成中")
            download_button = driver.find_element(By.ID, "saveCaptureBtn")
            download_button.click()
            time.sleep(5)

            # 获取目录里最新的图片
            downloaded_files = os.listdir(absolute_path)
            downloaded_files = [f for f in downloaded_files if os.path.isfile(os.path.join(absolute_path, f))]
            latest_file = max(
                downloaded_files,
                key=lambda f: os.path.getmtime(os.path.join(absolute_path, f))
            )
            # 返回最新文件的完整路径
            print("路径:",os.path.join(absolute_path, latest_file))
            return os.path.join(absolute_path, latest_file)
        finally:
            # 关闭浏览器
            driver.quit()
