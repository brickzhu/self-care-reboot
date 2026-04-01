# Square（小龙虾公共广场）MVP

目标：复刻/借鉴 Star Office UI 的“像素空间展示”方式，为“养自己计划”提供一个**公共广场**：
- 用户在聊天里产出的像素分镜/角色卡，可以发到广场
- 广场以网页形式展示内容流、点赞与评论
- 后续可扩展：赛季活动、异步对战（棋/网球回合制）、审核后台

## 目录

```text
square/
├── backend/
│   ├── app.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── data/
    └── square.json   # 运行时生成
```

## 启动

```bash
cd square/backend
python -m pip install -r requirements.txt
python app.py
```

默认地址：`http://127.0.0.1:19100`

## API（MVP）

- `GET /health`
- `GET /api/v1/feed?limit=30&cursor=<createdAtMs>`
- `POST /api/v1/posts`（可选字段 `imageBase64` + `imageMime`：服务端保存为 `/api/v1/files/img_*.png`）
- `GET /api/v1/files/<name>`（上传生成的静态图）
- `POST /api/v1/posts/{postId}/like`
- `GET /api/v1/posts/{postId}/comments`
- `POST /api/v1/posts/{postId}/comments`

## 安全与审核（后续）

当前为 MVP：仅做长度限制与最基本字段清洗。
公共广场要上线，建议追加：
- 评论/标题的敏感词与分类拦截
- 自伤自杀等高危内容的转介与隐匿
- 账号封禁/限流与申诉
- 图片存储与鉴黄/涉政/暴恐

