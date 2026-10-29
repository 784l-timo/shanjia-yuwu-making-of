# 学习细节与片头预演 v2

直接打开 `index.html` 即可离线观看；它内嵌视频、人声、海报和字幕，单独复制此 HTML 也可播放。

视频为 `善假于物_配音预演_v2_学习细节与片头.mp4`。独立片头图片在 `assets/片头海报_善假于物.png`。

总长 215.64 秒。片头新加 3 秒海报；原片整体后移 3 秒；片尾最后新加的 3 秒只是书桌静帧预留，设计待讨论。配音仍为 AI 预演人声。

## 修改与重建

1. 修改 `render_screens.cjs` 内的五组学习内容，运行 `node render_screens.cjs` 重新生成可编辑 HTML 与 1080p 画面。该脚本使用本机已有 Playwright；浏览器启动需相应系统权限。
2. 在此目录运行 `python3 build_v2.py`，重新合成视频、字幕和单文件预览。只调用本地 FFmpeg/ffprobe，不调用在线语音服务。
3. 运行 `node render_screens.cjs --build`，刷新学习界面并检查离线预览；如果 `verification.json` 已存在，该命令复用已验证视频。修改画面后应先完成第 2 步，避免复用旧视频。

重建仍依赖相邻原版 `../edit/` 和项目 `全片预演_HyperFrames/assets/`，保留它们。无需修改原 Windows 制作脚本，也无需重新生成配音。

验证记录：`verification.json`、`screen-verification.json`、`browser-verification.json`。
