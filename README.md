# ShowMeNav

## 介绍
一个可以查询基金净值的插件, 目前只支持播报给群友哦

## 安装

配置完成 [LangBot](https://github.com/RockChinQ/LangBot) 主程序后使用管理员账号向机器人发送命令即可安装：

```
!plugin get https://github.com/exneverbur/ShowMeNav.git
```
或查看详细的[插件安装说明](https://docs.langbot.app/plugin/plugin-intro.html#%E6%8F%92%E4%BB%B6%E7%94%A8%E6%B3%95)

## 使用

根据你的chrome浏览器版本在[此链接](https://registry.npmmirror.com/binary.html?path=chrome-for-testing/)下载对应的chrome driver

注意 driver的版本必须和你自己的chrome浏览器版本对应

然后在main.py中配置你的chrome driver的路径

|    指令    |                 含义                 | 示例   |
|:--------:|:----------------------------------:|------|
| $查询 基金代码 |           实时获取对应基金的当前估值            | $查询 320007 |
| $订阅 基金代码 |         订阅此基金，播报时将会查询此基金估值         |    $订阅 320007   |
|  $推送基金   |              立即推送一次播报              |                 |

每日自动播报时间如下(可自行在main.py内配置)：

['10:00', '12:00', '14:00', '14:50']

使用此插件时将会自动生成一个show_me_nav.json文件保存在langbot根目录下, 其中包含各个群的订阅信息。若需要清空所有订阅信息, 删除此文件即可。