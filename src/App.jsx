import { useMemo, useRef, useState } from 'react';
import {
  Check,
  Clock3,
  Database,
  Download,
  FileImage,
  FileSpreadsheet,
  Home,
  LogOut,
  PencilLine,
  RefreshCcw,
  RotateCcw,
  SearchCheck,
  ShieldCheck,
  Trash2,
  Upload,
  UserRound,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

const sampleRows = [
  { id: 1, question: '您的性别是？', answer: '男', confidence: 98, status: '已确认', type: '单选题', options: ['男', '女'] },
  { id: 2, question: '您的年龄段是？', answer: '25-35岁', confidence: 95, status: '已确认', type: '单选题', options: ['18-24岁', '25-35岁', '36-45岁', '46岁以上'] },
  { id: 3, question: '您的教育程度是？', answer: '本科', confidence: 96, status: '已确认', type: '单选题', options: ['高中及以下', '专科', '本科', '研究生及以上'] },
  { id: 4, question: '您使用本产品的频率是？', answer: '每周1-3次', confidence: 88, status: '待确认', type: '单选题', options: ['每天多次', '每天1次', '每周1-3次', '每月4次以上', '很少使用'] },
  { id: 5, question: '您最常使用的功能是？（多选）', answer: 'A、B、D', confidence: 90, status: '待确认', type: '多选题', options: ['A 数据录入', 'B 报表查看', 'C 消息提醒', 'D 数据导出'] },
  { id: 6, question: '您对本产品的满意度是？', answer: '满意', confidence: 93, status: '已确认', type: '单选题', options: ['非常满意', '满意', '一般', '不满意'] },
  { id: 7, question: '您是否会推荐本产品给他人？', answer: '是', confidence: 97, status: '已确认', type: '单选题', options: ['是', '否', '不确定'] },
  { id: 8, question: '您对本产品有哪些建议或意见？', answer: '界面可以更简洁一些', confidence: 85, status: '待确认', type: '填空题', options: [] },
];

const initialFiles = [
  { id: 'seed-1', name: '问卷_001.jpg', size: '2.34 MB', status: '识别中 65%', progress: 65 },
  { id: 'seed-2', name: '问卷_002.jpg', size: '1.98 MB', status: '排队中', progress: 0 },
  { id: 'seed-3', name: '问卷_003.jpg', size: '2.21 MB', status: '排队中', progress: 0 },
  { id: 'seed-4', name: '问卷_004.jpg', size: '1.76 MB', status: '等待中', progress: 0 },
  { id: 'seed-5', name: '问卷_005.jpg', size: '2.02 MB', status: '等待中', progress: 0 },
];

const historyRows = [
  { id: 'TASK-20260520-0001', name: '产品体验问卷_0520', count: 5, created: '2026-05-20 10:23:45', done: '-', status: '处理中' },
  { id: 'TASK-20260519-0003', name: '客户满意度调查_0519', count: 12, created: '2026-05-19 16:45:22', done: '2026-05-19 16:48:31', status: '已完成' },
  { id: 'TASK-20260518-0002', name: '市场调研问卷_0518', count: 8, created: '2026-05-18 09:12:11', done: '2026-05-18 09:15:07', status: '已完成' },
  { id: 'TASK-20260517-0001', name: '员工反馈问卷_0517', count: 15, created: '2026-05-17 14:33:05', done: '2026-05-17 14:37:42', status: '已完成' },
];

function formatBytes(bytes) {
  if (!bytes) return '0 MB';
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function App() {
  const fileInputRef = useRef(null);
  const [files, setFiles] = useState(initialFiles);
  const [rows, setRows] = useState(sampleRows);
  const [selectedId, setSelectedId] = useState(4);
  const [note, setNote] = useState('');
  const [isUploading, setUploading] = useState(false);
  const [taskId, setTaskId] = useState('TASK-20260520-0001');
  const [lastMessage, setLastMessage] = useState('演示数据已载入，可直接校正或导出。');
  const [recognitionMode, setRecognitionMode] = useState('演示数据');
  const [recognitionDetail, setRecognitionDetail] = useState('当前使用内置演示数据。');

  const selectedRow = rows.find((row) => row.id === selectedId) || rows[0];
  const confirmedCount = rows.filter((row) => row.status === '已确认').length;
  const taskProgress = Math.round((confirmedCount / rows.length) * 100);

  const totalSize = useMemo(() => {
    const seedTotal = files.reduce((sum, item) => {
      const number = Number.parseFloat(String(item.size).replace(' MB', ''));
      return sum + (Number.isNaN(number) ? 0 : number);
    }, 0);
    return seedTotal.toFixed(2);
  }, [files]);

  async function uploadFiles(event) {
    const selected = Array.from(event.target.files || []);
    if (!selected.length) return;
    const localFiles = selected.map((file, index) => ({
      id: `${Date.now()}-${index}`,
      name: file.name,
      size: formatBytes(file.size),
      status: index === 0 ? '上传中' : '排队中',
      progress: index === 0 ? 35 : 0,
    }));
    setFiles(localFiles);
    setUploading(true);
    setLastMessage('正在上传图片并创建识别任务。');

    try {
      const formData = new FormData();
      selected.forEach((file) => formData.append('files', file));
      const response = await fetch(`${API_BASE}/api/tasks`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) throw new Error('上传失败');
      const data = await response.json();
      setTaskId(data.task.id);
      setFiles(data.task.files);
      setRows(data.results);
      setSelectedId(data.results[0]?.id || 1);
      setRecognitionMode(data.task.llmUsed ? 'AI增强模式' : (data.task.mode === 'ocr' ? 'OCR识别模式' : '轻量识别模式'));
      setRecognitionDetail(data.task.llmMessage || (data.task.mode === 'ocr' ? '已启用 PaddleOCR/EasyOCR 文字识别和 OpenCV 候选选项框检测。' : 'OCR模型暂不可用，已读取上传图片并完成基础图像分析。'));
      setLastMessage(data.task.llmUsed ? '大模型结构化增强已完成，结果可在表格中校正。' : (data.task.mode === 'ocr' ? 'OCR识别任务已完成，结果可在表格中校正。' : `OCR暂不可用，已降级为轻量识别。${data.task.modeError || ''}`));
    } catch (error) {
      setFiles(localFiles.map((item, index) => ({
        ...item,
        status: index === 0 ? '识别中 65%' : item.status,
        progress: index === 0 ? 65 : 0,
      })));
      setRows(sampleRows);
      setRecognitionMode('后端未连接');
      setRecognitionDetail('前端没有连上 127.0.0.1:8000，上传不会进入后端识别。');
      setLastMessage('后端服务未启动，当前只能显示本地演示结果。请先启动 8000 后端。');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  }

  function updateAnswer(answer) {
    setRows((current) => current.map((row) => (
      row.id === selectedRow.id ? { ...row, answer, status: '待确认' } : row
    )));
  }

  function confirmSelected() {
    setRows((current) => current.map((row) => (
      row.id === selectedRow.id ? { ...row, status: '已确认', note } : row
    )));
    setLastMessage(`第 ${selectedRow.id} 题已保存校正结果。`);
  }

  function markProblem() {
    setRows((current) => current.map((row) => (
      row.id === selectedRow.id ? { ...row, status: '需复核' } : row
    )));
    setLastMessage(`第 ${selectedRow.id} 题已标记为需复核。`);
  }

  async function exportExcel() {
    try {
      const response = await fetch(`${API_BASE}/api/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ taskId, rows }),
      });
      if (!response.ok) throw new Error('导出失败');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${taskId}_识别结果.xlsx`;
      link.click();
      URL.revokeObjectURL(url);
      setLastMessage('Excel 文件已导出。');
    } catch (error) {
      const csv = ['题号,题目,答案,置信度,状态']
        .concat(rows.map((row) => `${row.id},"${row.question}","${row.answer}",${row.confidence},${row.status}`))
        .join('\n');
      const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${taskId}_识别结果.csv`;
      link.click();
      URL.revokeObjectURL(url);
      setLastMessage('未连接后端时已导出 CSV 结果。');
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">
          <ShieldCheck size={24} />
          <span>问卷识别</span>
        </div>
        <nav className="nav-list" aria-label="主导航">
          <NavItem icon={<Home size={20} />} active label="任务中心" />
          <NavItem icon={<Upload size={20} />} label="图片上传" />
          <NavItem icon={<SearchCheck size={20} />} label="识别结果" />
          <NavItem icon={<PencilLine size={20} />} label="人工校正" />
          <NavItem icon={<Database size={20} />} label="历史任务" />
          <NavItem icon={<FileSpreadsheet size={20} />} label="数据导出" />
        </nav>
        <div className="storage-card">
          <span>存储空间</span>
          <div className="storage-track">
            <i style={{ width: '25%' }} />
          </div>
          <strong>2.45 GB / 10.00 GB</strong>
        </div>
        <span className="version">系统版本：V1.0.0</span>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <h1>问卷图像识别与数据导出系统 V1.0</h1>
          <div className="top-actions">
            <span className="user-chip"><UserRound size={18} /> 张三 <i /> 在线</span>
            <button className="icon-button" title="退出登录"><LogOut size={18} />退出登录</button>
          </div>
        </header>

        <section className="content-grid">
          <div className="panel upload-panel">
            <PanelHeader title={`上传队列（${files.length}）`} />
            <div className="button-row">
              <button className="primary-button" onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
                <Upload size={16} /> 选择图片
              </button>
              <button className="secondary-button"><RefreshCcw size={16} /> 继续上传</button>
              <button className="danger-button" onClick={() => setFiles([])}><Trash2 size={16} /> 清空</button>
              <input ref={fileInputRef} className="hidden-input" type="file" accept=".jpg,.jpeg,.png" multiple onChange={uploadFiles} />
            </div>
            <div className="file-table">
              <div className="file-head"><span>文件名</span><span>大小</span><span>状态</span></div>
              {files.map((file) => (
                <button
                  className={`file-row ${file.progress > 0 ? 'selected' : ''}`}
                  key={file.id}
                  onClick={() => setLastMessage(`当前查看：${file.name}`)}
                >
                  <span className="thumb"><FileImage size={22} /></span>
                  <span className="file-name">{file.name}</span>
                  <span>{file.size}</span>
                  <StatusText file={file} />
                </button>
              ))}
            </div>
            <div className="queue-total">共 {files.length} 个文件，总大小 {totalSize} MB</div>
          </div>

          <div className="center-stack">
            <div className="panel process-panel">
              <PanelHeader title="处理流程" />
              <div className={`mode-banner ${recognitionMode === '后端未连接' ? 'offline' : ''}`}>
                <strong>{recognitionMode}</strong>
                <span>{recognitionDetail}</span>
              </div>
              <div className="stepper">
                {['上传图片', '图像预处理', 'OCR识别', '选项识别', '结果生成'].map((label, index) => (
                  <div className={`step ${index < 3 ? 'done' : index === 3 ? 'current' : ''}`} key={label}>
                    <span>{index + 1}</span>
                    <p>{label}</p>
                    <small>{index < 3 ? `${5 - index}/5` : index === 3 ? '2/5' : '等待中'}</small>
                  </div>
                ))}
              </div>
              <div className="progress-card">
                <div><span>当前任务：</span><strong>{files[0]?.name || '暂无任务'}</strong><b>{taskProgress}%</b></div>
                <div className="progress-track"><i style={{ width: `${Math.max(65, taskProgress)}%` }} /></div>
                <p>正在进行：选项检测与识别 <span>预计剩余时间：00:00:18</span></p>
              </div>
            </div>

            <div className="panel result-panel">
              <div className="panel-titlebar">
                <h2>识别结果预览（{files[0]?.name || '问卷_001.jpg'}）</h2>
                <div className="confidence">置信度：{Math.round(rows.reduce((sum, row) => sum + row.confidence, 0) / rows.length)}%</div>
                <button className="secondary-button compact"><RefreshCcw size={15} /> 刷新</button>
                <select aria-label="显示题目范围">
                  <option>显示：全部题目</option>
                  <option>仅待确认</option>
                  <option>仅需复核</option>
                </select>
              </div>
              <table className="result-table">
                <thead>
                  <tr>
                    <th>题号</th>
                    <th>题目内容</th>
                    <th>识别结果</th>
                    <th>置信度</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className={row.id === selectedRow.id ? 'active-row' : ''} onClick={() => setSelectedId(row.id)}>
                      <td>{row.id}</td>
                      <td>{row.question}</td>
                      <td>{row.answer}</td>
                      <td>{row.confidence}%</td>
                      <td><StatusBadge status={row.status} /></td>
                      <td><button className="link-button" onClick={() => setSelectedId(row.id)}>校正</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="table-footer">
                <span>共 {rows.length} 题</span>
                <div className="pager"><button disabled>‹</button><strong>1</strong><button>›</button><select><option>20 条/页</option></select></div>
              </div>
            </div>

            <div className="panel batch-panel">
              <strong>批量操作</strong>
              <span>已选择 {rows.filter((row) => row.status !== '已确认').length} 项</span>
              <button className="secondary-button">批量确认</button>
              <button className="secondary-button teal">批量校正</button>
              <button className="danger-button">标记有问题</button>
              <button className="secondary-button"><RotateCcw size={15} /> 重新识别</button>
            </div>
          </div>

          <aside className="right-stack">
            <div className="panel task-info">
              <PanelHeader title="任务信息" />
              <InfoRow label="任务ID：" value={taskId} />
              <InfoRow label="创建时间：" value="2026-06-24 10:23:45" />
              <InfoRow label="图片数量：" value={`${files.length} 张`} />
              <InfoRow label="完成数量：" value={`${confirmedCount} 题`} />
              <InfoRow label="任务状态：" value="处理中" tone="teal" />
            </div>

            <div className="panel inspector">
              <div className="tabs"><button className="active">题目详情</button><button>原图预览</button></div>
              <h3>题目 {selectedRow.id}：{selectedRow.question}</h3>
              <p>题型：{selectedRow.type}</p>
              <label className="field-label">识别结果</label>
              <input value={selectedRow.answer} onChange={(event) => updateAnswer(event.target.value)} />
              {selectedRow.options.length > 0 && (
                <>
                  <label className="field-label">选项列表</label>
                  <div className="option-list">
                    {selectedRow.options.map((option) => (
                      <label key={option} className={selectedRow.answer.includes(option) ? 'checked' : ''}>
                        <input
                          type={selectedRow.type === '多选题' ? 'checkbox' : 'radio'}
                          name="answer"
                          checked={selectedRow.answer.includes(option)}
                          onChange={() => updateAnswer(option)}
                        />
                        <span>{option}</span>
                        <em>{selectedRow.answer.includes(option) ? `选中（${selectedRow.confidence}%）` : '未选中'}</em>
                      </label>
                    ))}
                  </div>
                </>
              )}
              <label className="field-label">校正操作</label>
              <div className="correction-row">
                <button className="primary-button" onClick={confirmSelected}><Check size={16} /> 确认正确</button>
                <button className="warning-button" onClick={() => setLastMessage('已进入修改选择模式。')}><PencilLine size={16} /> 修改选择</button>
                <button className="danger-button" onClick={() => updateAnswer('')}><Trash2 size={16} /> 清除选择</button>
              </div>
              <textarea placeholder="请输入备注信息（可选）" value={note} onChange={(event) => setNote(event.target.value)} />
              <button className="mark-button" onClick={markProblem}>标记为需复核</button>
            </div>
          </aside>
        </section>

        <section className="panel history-panel">
          <div className="panel-titlebar">
            <h2>任务历史</h2>
            <div className="history-actions">
              <button className="secondary-button"><Clock3 size={15} /> 查看更多历史</button>
              <button className="primary-button" onClick={exportExcel}><Download size={16} /> 导出全部结果（Excel）</button>
            </div>
          </div>
          <table className="history-table">
            <thead>
              <tr><th>任务ID</th><th>任务名称</th><th>图片数量</th><th>创建时间</th><th>完成时间</th><th>状态</th><th>操作</th></tr>
            </thead>
            <tbody>
              {historyRows.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td><td>{row.name}</td><td>{row.count}</td><td>{row.created}</td><td>{row.done}</td>
                  <td><StatusBadge status={row.status} /></td>
                  <td><button className="link-button">查看</button><button className="link-button">导出</button><button className="link-button red">删除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <div className="toast" role="status">{lastMessage}</div>
      </main>
    </div>
  );
}

function NavItem({ icon, label, active }) {
  return <button className={`nav-item ${active ? 'active' : ''}`}>{icon}<span>{label}</span></button>;
}

function PanelHeader({ title }) {
  return <div className="panel-heading"><h2>{title}</h2></div>;
}

function InfoRow({ label, value, tone }) {
  return <div className="info-row"><span>{label}</span><strong className={tone}>{value}</strong></div>;
}

function StatusText({ file }) {
  if (file.progress > 0) return <span className="file-status teal"><span className="spinner" />{file.status}</span>;
  if (file.status.includes('排队')) return <span className="file-status blue"><Clock3 size={16} />{file.status}</span>;
  return <span className="file-status muted"><Clock3 size={16} />{file.status}</span>;
}

function StatusBadge({ status }) {
  const className = status === '已确认' || status === '已完成' ? 'ok' : status === '需复核' ? 'danger' : status === '处理中' ? 'processing' : 'pending';
  return <span className={`status-badge ${className}`}>{status}</span>;
}

export default App;
