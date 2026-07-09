# 问卷图像识别与数据导出系统 V1.0

这是一个前后端分离的软件原型，用于纸质问卷、扫描问卷和拍照问卷的上传、识别结果预览、人工校正、历史任务管理和 Excel 导出。

## 功能

- 用户工作台与任务导航
- JPG、JPEG、PNG 批量上传
- 图像预处理、OCR、勾选框检测流程展示
- 结构化识别结果表格
- 题目答案人工校正与复核标记
- 历史任务列表
- Excel 导出，后端不可用时前端降级导出 CSV

## 启动前端

```bash
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5173`

Windows 下也可以直接双击 `start-frontend.bat`。

## 启动后端

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：`http://127.0.0.1:8000`

Windows 下也可以直接双击 `start-backend.bat`。

## 可选：启用大模型结构化增强

系统默认可直接使用 OCR + OpenCV + 规则解析。若需要让大模型对 OCR 结果进行结构化整理和纠错，可在启动后端前设置以下环境变量：

```bash
LLM_API_KEY=你的API密钥
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=模型名称
LLM_TIMEOUT=60
```

也可以参考 `backend/.env.example`。后端调用的是 OpenAI 兼容的 `/chat/completions` 接口，因此可接入支持该接口格式的模型服务。大模型只处理 OCR 文本、坐标和候选勾选框结果，不直接接收原始图片。

## 说明

当前版本提供完整业务闭环和可替换的接口结构。上传图片后，后端会读取图片，优先使用 PaddleOCR 执行中文问卷文字识别；如果 PaddleOCR 不可用，会回退到 EasyOCR，并使用 OpenCV 检测候选选项框；如果配置了大模型接口，系统会进一步调用大模型进行结构化解析与纠错；如果所有 OCR 模型均不可用，会自动降级为轻量图像分析，返回图片尺寸、深色像素占比和候选选项框数量。

首次执行 OCR 时模型加载会比较慢，终端可能下载或初始化模型，这是正常现象。当前 Windows/Python 3.12 环境已锁定 `paddlepaddle==3.0.0`、`paddleocr<3`、`albumentations<2`，用于避开 PaddleOCR 3.x 依赖链和 PaddlePaddle 3.2+ 的 oneDNN 推理问题。CPU 模式能用但速度较慢。
