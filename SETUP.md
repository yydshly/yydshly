# yydshly 的 GitHub 个人主页

这个目录是一份独立的个人主页仓库内容。根目录的 README.md 是实际显示在 GitHub 个人主页上的内容。

## 启用主页

1. 在 yydshly 账号下创建公开仓库 yydshly，默认分支使用 main。
2. 把本目录的内容提交到该仓库根目录，包括隐藏的 .github 文件夹。
3. 在 Actions 页面查看 Update terminal profile 工作流，首次提交会自动生成统计，也可以通过 Run workflow 手动运行。
4. 访问 https://github.com/yydshly 查看主页。

GitHub 要求个人主页仓库名称与用户名相同、仓库公开且根目录包含非空 README.md。主页图片会跟随 GitHub 的明暗主题，手机宽度会选择单列图片。

## 修改内容

编辑 profile.json 中的简介、终端字段、项目列表和项目入口。当前简介根据公开仓库概括，头像使用账号的公开 GitHub 头像。Uptime 表示 GitHub 账号使用天数。

图片和 README.md 由脚本生成，修改后执行以下命令重新生成。

```powershell
python -m pip install -r requirements.txt
python scripts/update_profile.py
```

已经保存一份仅包含公开统计的 assets/public-data.json，可离线重新渲染。

```powershell
python scripts/update_profile.py --offline
```

## 自动更新

工作流设为每天 UTC 04:23 运行，对应北京时间 12:23。GitHub 计划任务可能延迟。它使用仓库自带的 GITHUB_TOKEN，仅请求公开用户与公开仓库接口。仓库统计支持分页，可覆盖超过 100 个公开仓库的账号。

Repos 包含账号的所有公开仓库。Originals、Stars 与语言排序只计算非 fork 公开仓库。Languages 表示仓库主语言出现次数，不能代表个人熟练度。头像、账号天数与统计在同一次构建中更新，图片页脚标记同步时间。请求失败时工作流报错并保留已提交版本。

## 设计参考

终端名片形式参考 https://github.com/Andrew6rant/Andrew6rant 。本仓库脚本和 SVG 由当前账号的数据重新制作。
