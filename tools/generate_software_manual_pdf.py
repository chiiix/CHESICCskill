from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "问卷图像识别与数据导出系统V1.0_软件说明书.pdf"
FONT_DIR = Path("C:/Windows/Fonts")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("SoftSong", str(FONT_DIR / "simsun.ttc")))
    pdfmetrics.registerFont(TTFont("SoftHei", str(FONT_DIR / "msyh.ttc")))


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="SoftHei",
            fontSize=20,
            leading=28,
            textColor=colors.HexColor("#172033"),
            alignment=1,
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="SoftHei",
            fontSize=15,
            leading=22,
            textColor=colors.HexColor("#172033"),
            spaceBefore=12,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="SoftHei",
            fontSize=12.5,
            leading=18,
            textColor=colors.HexColor("#243047"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="SoftSong",
            fontSize=10.5,
            leading=18,
            firstLineIndent=21,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=6,
        ),
        "list": ParagraphStyle(
            "list",
            parent=base["BodyText"],
            fontName="SoftSong",
            fontSize=10.5,
            leading=18,
            leftIndent=14,
            firstLineIndent=-10,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["BodyText"],
            fontName="SoftSong",
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#536175"),
        ),
    }


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), style)


def table(data: list[list[str]], style: dict[str, ParagraphStyle]) -> Table:
    wrapped = [[p(cell, style["small"]) for cell in row] for row in data]
    t = Table(wrapped, colWidths=[38 * mm, 118 * mm])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd8e5")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4f8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def footer(canvas, doc) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setFont("SoftSong", 8)
    canvas.setFillColor(colors.HexColor("#687386"))
    canvas.drawString(18 * mm, 10 * mm, "问卷图像识别与数据导出系统V1.0 软件说明书")
    canvas.drawRightString(192 * mm, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build_story() -> list:
    s = styles()
    story: list = []
    story.append(p("问卷图像识别与数据导出系统V1.0<br/>软件说明书", s["title"]))
    story.append(Spacer(1, 8 * mm))
    story.append(
        table(
            [
                ["项目", "内容"],
                ["软件名称", "问卷图像识别与数据导出系统V1.0"],
                ["软件版本", "V1.0"],
                ["软件类型", "图像识别、OCR文字识别、问卷数据结构化与数据导出软件"],
                ["运行方式", "本地或服务器部署，浏览器访问前端页面，后端提供识别与导出接口"],
                ["主要技术", "React、Vite、FastAPI、SQLite、PaddleOCR、EasyOCR、OpenCV、openpyxl"],
            ],
            s,
        )
    )
    story.append(PageBreak())

    sections = [
        (
            "一、软件概述",
            [
                "问卷图像识别与数据导出系统V1.0是一套面向纸质问卷、扫描问卷和拍照问卷的数据识别与整理软件。系统通过浏览器页面完成问卷图片上传，后端对图片进行OCR文字识别和候选勾选框检测，并将识别结果整理成结构化数据，供用户预览、校正和导出。",
                "本软件主要用于减少传统问卷人工录入工作量，提高纸质问卷电子化处理效率，降低人工录入错误率。系统适用于问卷调查、心理测评、教学测验、社会调查、满意度调查和数据采集等场景。",
            ],
        ),
        (
            "二、运行环境",
            [
                "客户端运行环境为Chrome、Edge等现代浏览器。服务端运行环境为Windows 10或Windows 11，Python 3.12及以上环境，Node.js运行环境，以及本地文件存储目录。",
                "前端采用React与Vite构建，后端采用FastAPI提供接口服务。图像识别能力优先使用PaddleOCR，PaddleOCR不可用时回退至EasyOCR；候选选项框检测使用OpenCV实现；Excel文件导出使用openpyxl生成。",
            ],
        ),
        (
            "三、软件功能结构",
            [
                "系统主要包括用户工作台、图片上传、识别任务管理、图像识别处理、结果预览、人工校正、历史任务管理和数据导出等模块。",
                "前端模块负责页面展示、文件选择、上传进度显示、识别状态反馈、表格预览、答案编辑和导出触发。后端模块负责文件接收、图片存储、OCR识别、候选选项框检测、识别结果结构化、任务记录保存和Excel文件输出。",
            ],
        ),
        (
            "四、主要功能说明",
            [
                "1. 图片上传功能：用户可选择JPG、JPEG、PNG等格式的问卷图片，系统将图片上传至后端并创建识别任务。",
                "2. OCR文字识别功能：系统优先调用PaddleOCR识别图片中的中文和英文文本，获取文本内容、坐标位置和识别置信度。",
                "3. 勾选框检测功能：系统使用OpenCV对图片中的方框、圆形选项框等候选区域进行轮廓检测，并根据填充比例判断候选勾选状态。",
                "4. 结构化解析功能：系统根据OCR文本位置、选项框位置和勾选状态生成题目、答案、置信度、状态等结构化字段。",
                "5. 人工校正功能：用户可在识别结果页面对题目文本、识别答案和备注信息进行修改，并可将异常数据标记为需复核。",
                "6. 数据导出功能：用户确认结果后，可将结构化问卷数据导出为Excel文件，便于后续统计分析和归档。",
            ],
        ),
        (
            "五、业务处理流程",
            [
                "系统处理流程为：用户上传问卷图片，后端保存原始文件，读取图片基础信息，调用OCR引擎识别文本，调用OpenCV检测候选选项框，将文字区域与选项框位置进行匹配，生成结构化识别结果，前端展示结果并支持人工校正，最后导出Excel文件。",
                "当PaddleOCR模型不可用时，系统会自动回退到EasyOCR；如果所有OCR模型均不可用，则执行轻量图像分析，至少返回图片尺寸、深色像素占比、候选选项框数量等基础信息，保证系统具有可用的兜底处理能力。",
            ],
        ),
        (
            "六、数据字段说明",
            [
                "识别结果主要字段包括任务ID、图片名称、题号、题目内容、识别答案、置信度、处理状态、题型和选项信息。任务管理字段包括任务编号、任务名称、创建时间、图片数量、处理状态和导出状态。",
                "导出的Excel文件按照任务ID、题号、题目内容、识别答案、置信度、处理状态、题型等字段组织，便于用户进行后续汇总、筛选、统计和分析。",
            ],
        ),
        (
            "七、操作说明",
            [
                "1. 启动后端服务：运行start-backend.bat，启动FastAPI服务，默认地址为http://127.0.0.1:8000。",
                "2. 启动前端服务：运行start-frontend.bat，启动Vite前端服务，默认地址为http://127.0.0.1:5173。",
                "3. 上传问卷图片：进入系统页面后点击选择图片，选择一张或多张问卷图片并上传。",
                "4. 查看识别结果：系统完成识别后，在识别结果预览表格中显示题目、答案、置信度和处理状态。",
                "5. 人工校正结果：用户点击表格中的校正项，在右侧详情区域修改识别结果或标记复核。",
                "6. 导出数据文件：确认识别结果后，点击导出全部结果按钮，下载Excel文件。",
            ],
        ),
        (
            "八、软件特点",
            [
                "本软件采用前后端分离结构，界面清晰，任务状态明确，便于用户批量上传和集中校正。系统同时支持OCR文字识别、候选选项框检测和Excel导出，覆盖纸质问卷电子化处理的核心流程。",
                "系统具有识别引擎回退机制，在PaddleOCR不可用时自动回退至EasyOCR或轻量图像分析，提高了不同运行环境下的可用性和稳定性。",
            ],
        ),
        (
            "九、适用范围",
            [
                "本软件适用于问卷调查数据录入、课堂测验结果整理、心理测评问卷电子化、市场调研问卷汇总、满意度调查统计和社会调查数据采集等业务场景。",
                "用户可将纸质问卷扫描或拍照后导入系统，通过识别、校正和导出流程，将非结构化图像资料转化为结构化表格数据。",
            ],
        ),
    ]

    for title, paragraphs in sections:
        story.append(p(title, s["h1"]))
        for paragraph in paragraphs:
            style = s["list"] if paragraph[:2].strip(".").isdigit() else s["body"]
            story.append(p(paragraph, style))
        story.append(Spacer(1, 3 * mm))
    return story


def build_pdf() -> Path:
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="问卷图像识别与数据导出系统V1.0_软件说明书",
    )
    doc.build(build_story(), onFirstPage=footer, onLaterPages=footer)
    return OUTPUT


if __name__ == "__main__":
    print(build_pdf())
