import gradio as gr
import google.generativeai as genai
import os
import asyncio
import pandas as pd
import io
import mimetypes
import html
import tempfile # <-- 最终修复点 1: 导入 tempfile 库

# --- Google API Key 配置 ---
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY 环境变量未设置。")

try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    raise RuntimeError(f"配置 Google GenAI 失败：{e}")

# --- 统一的模型映射字典 ---
MODEL_MAPPING = {
    "Gemini 2.5 Flash (快速高效)": "gemini-2.5-flash",
    "Gemini 2.5 Pro (深度理解)": "gemini-2.5-pro",
}


# --- 后台异步任务处理函数 ---
async def async_gemini_analysis_task(prompt: str, file_data: dict, model_id: str, semaphore: asyncio.Semaphore):
    filename, audio_bytes, mime_type = file_data['filename'], file_data['bytes'], file_data['type']
    try:
        async with semaphore:
            model = genai.GenerativeModel(model_id)
            response = await model.generate_content_async([prompt, {'mime_type': mime_type, 'data': audio_bytes}])
            return {'filename': filename, 'status': '✅ 完成', 'message': "分析成功", 'result': response.text, 'error_details': None}
    except genai.types.BlockedPromptException as e:
        return {'filename': filename, 'status': '⚠️ 被阻止', 'message': "请求因安全设置被阻止", 'result': None, 'error_details': str(e)}
    except Exception as e:
        return {'filename': filename, 'status': '❌ 失败', 'message': f"分析过程中发生错误: {type(e).__name__}", 'result': None, 'error_details': str(e)}


# --- Gradio 主处理函数 ---
async def analyze_audio_files(uploaded_files: list, selected_model_name: str, user_prompt: str, max_concurrent_workers: int):
    if not uploaded_files:
        gr.Warning("请上传至少一个音频文件！")
        yield ("", "任务中止：未提供文件。", "", "", gr.update(value=None, visible=False))
        return

    selected_model_id = MODEL_MAPPING.get(selected_model_name, "gemini-1.5-flash-latest")

    files_data_for_tasks, file_previews_html_list = [], []
    for idx, file_obj in enumerate(uploaded_files):
        temp_file_path = str(file_obj)
        filename = os.path.basename(file_obj.name)
        with open(temp_file_path, 'rb') as f:
            audio_bytes = f.read()
        mime_type, _ = mimetypes.guess_type(filename)
        files_data_for_tasks.append({'filename': filename, 'bytes': audio_bytes, 'type': mime_type or 'application/octet-stream'})
        file_previews_html_list.append(f"""<div style="margin-bottom: 10px;"><h4>文件 {idx+1}: {filename}</h4><audio controls src="file={temp_file_path}" style="width: 100%;"></audio><p>大小: {round(len(audio_bytes) / (1024 * 1024), 2)} MB</p></div>""")
    
    file_preview_markdown_content = f"""<div><h3>📤 已上传音频预览</h3>{"".join(file_previews_html_list)}</div>"""
    yield (file_preview_markdown_content, f"🚀 正在启动对 {len(uploaded_files)} 个文件的分析任务...", "", "", gr.update(visible=False))

    semaphore = asyncio.Semaphore(max_concurrent_workers)
    tasks = [async_gemini_analysis_task(user_prompt, data, selected_model_id, semaphore) for data in files_data_for_tasks]
    results = await asyncio.gather(*tasks)
    
    output_md, error_md, df_data = "<h3>📊 分析结果概览</h3>", "", []
    for idx, res in enumerate(results):
        result_safe = html.escape(res['result']) if res['result'] else ""
        output_md += f"""<div style="border: 1px solid #e0e0e0; padding: 15px; border-radius: 8px; margin-bottom: 15px;"><h4>文件 {idx+1}: {res['filename']} - 状态: <span style="font-weight:bold;">{res['status']}</span></h4><p><strong>消息:</strong> {res['message']}</p>"""
        if res['result']:
            output_md += f"<h5>分析结果:</h5><div style='background-color:#f9f9f9; padding: 10px; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word;'>{result_safe}</div>"
        if res['error_details']:
            error_md += f"""<div><h4>文件 {idx+1}: {res['filename']} - 错误: {res['message']}</h4><pre><code>{html.escape(str(res['error_details']))}</code></pre></div>"""
        output_md += "</div>"
        df_data.append({
            "文件名": res.get('filename'), "状态": res.get('status'), "消息": res.get('message'),
            "分析结果": res.get('result'), "错误详情": res.get('error_details')
        })

    df = pd.DataFrame(df_data)
    excel_name = f"gemini_audio_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    # --- 最终修复点 2: 创建一个临时文件来存储 Excel 数据 ---
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='AnalysisResults')
        # 获取临时文件的完整路径
        temp_file_path = tmp.name

    final_error_md = f"<h3>🐛 错误日志</h3>{error_md}" if error_md else ""
    
    # --- 最终修复点 3: 将临时文件的路径作为 value 传给 gr.update ---
    excel_update = gr.update(
        value=temp_file_path,
        label=f"下载报告 ({excel_name})", # 更新标签以显示友好的文件名
        visible=True,
        interactive=True
    )
    
    yield (gr.update(), "✅ 所有任务处理完毕。", output_md, final_error_md, excel_update)


# --- Gradio 界面定义 ---
with gr.Blocks(title="Gemini Audio Assistant", theme=gr.themes.Soft(primary_hue="sky")) as demo:
    gr.Markdown("# 🎵 Gemini 音频智能助手 ✨\n利用 Google Gemini 多模态模型，深度分析和理解您的音频内容。")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## ⚙️ 系统控制台")
            model_dropdown = gr.Dropdown(label="选择 AI 模型版本:", choices=list(MODEL_MAPPING.keys()), value=list(MODEL_MAPPING.keys())[0], type="value")
            file_uploader = gr.Files(label="拖放或点击上传音频文件", file_count="multiple", type="filepath", file_types=["audio"])
            prompt_textbox = gr.Textbox(label="输入您的分析指令或问题:", value="请详细描述这个音频剪辑的内容，识别其中的任何声音、音乐或语音。总结其主要信息。如果包含语音，请尝试转录关键信息。", lines=10, max_lines=20)
            max_workers_slider = gr.Slider(label="并发处理限制 (1-10个任务):", minimum=1, maximum=10, value=5, step=1)
            analyze_button = gr.Button("🚀 启动数据分析", variant="primary")
        with gr.Column(scale=2):
            file_preview_output = gr.Markdown("""<div style="text-align: center; padding: 50px; border: 2px dashed #ccc; border-radius: 10px;"><h2>🌐 欢迎来到 Gemini 音频分析平台</h2><p>请在左侧上传音频文件，输入您的指令，然后点击 '启动数据分析'。</p></div>""")
            info_message_output = gr.Textbox(label="状态信息", value="等待任务...", interactive=False)
            analysis_results_output = gr.Markdown()
            error_details_output = gr.Markdown()
            excel_output = gr.File(label="下载分析结果", visible=False, interactive=False)

    outputs_list = [file_preview_output, info_message_output, analysis_results_output, error_details_output, excel_output]
    analyze_button.click(fn=analyze_audio_files, inputs=[file_uploader, model_dropdown, prompt_textbox, max_workers_slider], outputs=outputs_list)

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", 7860)), show_api=False, debug=True)