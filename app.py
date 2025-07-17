import streamlit as st
import google.generativeai as genai
from google.generativeai import protos # 导入 protos 模块，用于构建内嵌二进制数据
import os
import pandas as pd # <-- 导入 pandas
import io # <-- 导入 io，用于处理 BytesIO 内存文件流

# --- Streamlit 页面配置 ---
st.set_page_config(
    page_title="🎵 Gemini 音频智能助手 (批量)",
    page_icon="✨",
    layout="wide", # 使用宽布局，充分利用屏幕空间
    initial_sidebar_state="expanded" # 侧边栏默认展开
)

# --- 顶部标题和描述 ---
st.markdown("<h1 style='text-align: center; color: #4CAF50;'>🎵 Gemini 音频智能助手 (批量) ✨</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: grey;'>利用 Google Gemini 多模态模型，批量分析您的音频内容并生成报告。</p>", unsafe_allow_html=True)
st.divider() # 一条漂亮的分割线

# --- Google API Key 配置 ---
# 直接从环境变量获取 API Key (推荐用于部署，如 Zeabur)
api_key = os.getenv("GOOGLE_API_KEY")

# API Key 提示与配置引导
if not api_key:
    st.warning("⚠️ **Google API Key 未设置！** 请在继续之前配置。", icon="🔑")
    st.info("""
    **配置方式：**
    - **部署到 Zeabur**: 在 Zeabur 控制台的环境变量中添加 `GOOGLE_API_KEY = "your_api_key_here"`
    - **本地运行**: 在终端中设置环境变量 `export GOOGLE_API_KEY="your_api_key_here"`
    """)
    st.stop() # 如果没有 API Key，停止应用运行

# 配置 Google Generative AI 客户端
try:
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"❌ 配置 Google GenAI 客户端失败：{e}", icon="⛔")
    st.exception(e) # 显示详细的异常信息，方便调试
    st.stop()

# --- 侧边栏：操作面板 ---
st.sidebar.header("⚙️ 操作面板")

# 模型选择
st.sidebar.subheader("🤖 选择 Gemini 模型")
model_options = {
    "Gemini 2.5 Flash (快速高效)": "gemini-2.5-flash",
    "Gemini 2.5 Pro (深度理解)": "gemini-2.5-pro",
}
selected_model_name = st.sidebar.selectbox(
    "模型版本:",
    options=list(model_options.keys()),
    index=0, # 默认选中第一个 Flash 模型
    help="Gemini 2.5 Flash 速度更快、成本更低，适合快速概括；Gemini 2.5 Pro 功能更强大，理解更深入，但可能响应稍慢且成本更高。"
)
selected_model_id = model_options[selected_model_name]

st.sidebar.divider() # 分割线

# 音频文件上传 (支持多文件)
st.sidebar.subheader("📤 上传音频文件 (最多 50 个)")
uploaded_files = st.sidebar.file_uploader(
    "选择一个或多个音频文件 (.mp3, .wav, .flac 等)",
    type=["mp3", "wav", "flac", "ogg", "m4a"], # 支持常见音频格式
    accept_multiple_files=True, # <-- 允许上传多个文件
    help="支持的音频格式包括 MP3、WAV、FLAC、OGG、M4A 等。请注意，直接内嵌音频到请求中通常适合**较短**的音频片段（建议文件大小在几MB以内，例如1-4分钟），过大文件可能导致请求失败或超时。单个批次最多支持 50 个文件。"
)

# 文件数量限制检查
MAX_FILES = 50
if uploaded_files and len(uploaded_files) > MAX_FILES:
    st.sidebar.warning(f"⚠️ 您上传了 {len(uploaded_files)} 个文件，但最大支持 {MAX_FILES} 个。请移除多余文件。", icon="🚫")
    uploaded_files = uploaded_files[:MAX_FILES] # 截断到最大数量

st.sidebar.divider() # 分割线

# Prompt 输入
st.sidebar.subheader("📝 定义您的分析任务")
default_prompt = "请详细描述这个音频剪辑的内容，识别其中的任何声音、音乐或语音。总结其主要信息。如果包含语音，请尝试转录关键信息。"
user_prompt = st.sidebar.text_area(
    "对模型说些什么？",
    value=default_prompt,
    height=300, # 增大高度，提供更好的输入体验
    help="输入您想让 Gemini 模型对音频执行的任务或提问。例如：'分析这段音乐的风格和情绪'、'转录这段对话的主要内容'等。"
)

st.sidebar.markdown("---") # 再一个分割线
analyze_button = st.sidebar.button("🚀 开始批量分析音频", use_container_width=True) # 按钮填满侧边栏宽度

# --- 主内容区域 ---
main_output_container = st.container()

with main_output_container:
    # 占位符，用于动态显示状态信息
    status_message_area = st.empty()
    # Expander 用于折叠和展开批处理概览
    batch_summary_expander = st.expander("📊 批处理概览", expanded=False)
    # Expander 用于折叠和展开 Gemini 分析结果
    analysis_results_container = st.container() # 结果区域，不再是expander，直接显示，但内部可以有expander

# --- 处理逻辑 ---
if analyze_button:
    if not uploaded_files: # 检查是否有文件上传
        status_message_area.warning("⚠️ 请先上传音频文件！", icon="⬆️")
        batch_summary_expander.empty()
        analysis_results_container.empty()
    else:
        # 清除之前的消息和结果，准备显示新的分析
        status_message_area.empty()
        batch_summary_expander.empty()
        analysis_results_container.empty()
        
        # 强制展开概览区域
        batch_summary_expander.expanded = True

        status_message_area.info(f"⏳ 正在开始分析 {len(uploaded_files)} 个音频文件，请稍候...", icon="🔄")
        
        results = [] # 存储所有文件的分析结果
        model = genai.GenerativeModel(selected_model_id) # 在循环外初始化模型，避免重复创建

        # --- 批处理进度条 ---
        progress_bar = status_message_area.progress(0)
        progress_text_placeholder = st.empty()

        for i, uploaded_file in enumerate(uploaded_files):
            file_name = uploaded_file.name
            file_size_mb = round(uploaded_file.size / (1024 * 1024), 2)
            
            progress_percentage = (i / len(uploaded_files))
            progress_bar.progress(progress_percentage)
            progress_text_placeholder.text(f"🚀 正在分析文件 {i+1}/{len(uploaded_files)}: `{file_name}` ({file_size_mb} MB)...")

            current_file_result = {"文件名称": file_name, "文件大小 (MB)": file_size_mb}
            
            with analysis_results_container:
                # 每个文件结果显示在一个独立的expander中，防止页面过长
                with st.expander(f"文件 {i+1}: `{file_name}` 分析结果", expanded=False):
                    st.audio(uploaded_file, format=uploaded_file.type, start_time=0, loop=False) # 提供音频预览
                    st.markdown(f"**MIME 类型:** `{uploaded_file.type}`")
                    st.markdown(f"**模型:** `{selected_model_name}`")
                    st.markdown(f"**Prompt:** `{user_prompt}`")
                    file_status_placeholder = st.empty() # 用于显示当前文件状态
                    file_result_placeholder = st.empty() # 用于显示当前文件结果

                    file_status_placeholder.info(f"开始分析 `{file_name}`...")

                    try:
                        audio_bytes = uploaded_file.getvalue()
                        
                        # 使用 google.generativeai.protos 显式构建 Part 对象
                        audio_part = protos.Part(
                            inline_data=protos.Blob(
                                data=audio_bytes,
                                mime_type=uploaded_file.type
                            )
                        )
                        
                        file_status_placeholder.info(f"正在向 Gemini 发送 `{file_name}` 请求...")
                        
                        response = model.generate_content(
                            contents=[user_prompt, audio_part]
                        )
                        
                        gemini_response_text = response.text
                        file_status_placeholder.success(f"✅ `{file_name}` 分析成功！")
                        file_result_placeholder.markdown(f"**Gemini 回复:**\n{gemini_response_text}")
                        current_file_result["Gemini 回复"] = gemini_response_text

                    except genai.types.BlockedPromptException as e:
                        error_msg = f"安全阻止：{e}"
                        file_status_placeholder.error(f"⚠️ `{file_name}` 分析失败：{error_msg}")
                        st.exception(e) # 显示详细异常
                        current_file_result["Gemini 回复"] = f"分析失败 (安全阻止): {error_msg}"
                    except Exception as e:
                        error_msg = f"意外错误：{e}"
                        file_status_placeholder.error(f"❌ `{file_name}` 分析失败：{error_msg}")
                        st.exception(e) # 显示详细异常
                        current_file_result["Gemini 回复"] = f"分析失败 (错误): {error_msg}"
            
            results.append(current_file_result)

        # 批处理完成
        progress_bar.progress(1.0)
        progress_text_placeholder.success(f"🎉 所有 {len(uploaded_files)} 个文件分析完成！")
        status_message_area.success("✅ 批处理完成！请查看下方概览和下载报告。", icon="🎉")

        # 将结果转换为 DataFrame
        df_results = pd.DataFrame(results)

        with batch_summary_expander:
            st.subheader("批处理概览")
            st.dataframe(df_results, use_container_width=True) # 显示结果表格

            # 提供 Excel 下载
            excel_buffer = io.BytesIO()
            df_results.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0) # 将游标移到文件开头

            st.download_button(
                label="📥 下载分析报告 (Excel)",
                data=excel_buffer,
                file_name="gemini_audio_analysis_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="点击下载包含所有文件分析结果的Excel报告。"
            )

# --- 页脚 (可选) ---
st.markdown("---")
st.markdown("""
    <p style='text-align: center; color: grey; font-size: 0.9em;'>
        由 Streamlit & Google Gemini API 驱动 🚀 <br>
        如果您喜欢这个应用，请分享给您的朋友！
    </p>
""", unsafe_allow_html=True)