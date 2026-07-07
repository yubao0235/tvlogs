import os
import json
import sys

# ================= ⚡ 跨库核心动态路径锁定 =================
# 优先读取 GitHub 工作流注入的私库绝对路径，若无则使用本地脚本上级目录
WORKSPACE = os.environ.get("LIVE_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 核心：将扫描根目录强行锚定为下载下来的私库
REPO_ROOT = WORKSPACE

# 最终生成的静态页面与账本路径全部锁死在私库中
HOTEL_DIR = os.path.join(WORKSPACE, "hotel")          
REBORN_DIR = os.path.join(WORKSPACE, "hotels")        
OUTPUT_INDEX = os.path.join(WORKSPACE, "index.html")   
OUTPUT_JSON = os.path.join(WORKSPACE, "snapshot.json") 
# ==========================================================

def generate_snapshot_and_portal():
    print("📡 [注意模式] 正在全力扫描私库文件结构...")
    
    # 1. 递归扫描私库中需要对外开放的静态资源
    valid_files = []
    
    # 定义允许前端查看和下载的文件后缀
    ALLOWED_EXTENSIONS = ('.m3u', '.txt', '.json')
    # 必须严格拦截和保密的隐私目录名
    EXCLUDE_DIRS = {'.git', '.github', '__pycache__'}

    for root, dirs, files in os.walk(REPO_ROOT):
        # 实时过滤掉不想暴露给前端的敏感/基础目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            if file.endswith(ALLOWED_EXTENSIONS):
                # 如果这个文件碰巧是即将生成的 index.html 本身或账本，不要塞入列表
                if file in ['index.html', 'snapshot.json']:
                    continue
                
                # 计算出相对于私库根目录的干净路径 (例如: "hotels/ALL.m3u", "md/traffic_report.txt")
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, REPO_ROOT).replace('\\', '/')
                valid_files.append(relative_path)

    # 按字母表自然排序，让前端生成的树形菜单极度舒适整齐
    valid_files.sort()

    # 2. 写入 snapshot.json 快照账本
    try:
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as fj:
            json.dump(valid_files, fj, ensure_ascii=False, indent=2)
        print(f"📦 云端快照账本生成成功: {len(valid_files)} 个资产已被登记到 snapshot.json")
    except Exception as e:
        print(f"❌ 写入快照账本失败: {e}")
        return

    # 3. 完美注入你提供的强力高级 HTML 模板代码
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPTV 私库云静态文件管理器</title>
    <style>
        :root {
            --bg-color: #f5f7fa;
            --panel-bg: #ffffff;
            --text-color: #2c3e50;
            --primary-color: #3498db;
            --border-color: #e2e8f0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container {
            width: 100%;
            max-width: 900px;
            background: var(--panel-bg);
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border: 1px solid var(--border-color);
            padding: 20px;
            box-sizing: border-box;
        }
        h2 {
            margin-top: 0;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--border-color);
            font-size: 1.4rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .tree-node {
            list-style: none;
            padding-left: 20px;
            margin: 6px 0;
        }
        .tree-root {
            padding-left: 0;
        }
        .folder, .file {
            cursor: pointer;
            padding: 6px 8px;
            border-radius: 4px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            user-select: none;
            transition: background 0.2s;
        }
        .folder:hover, .file:hover {
            background-color: #edf2f7;
        }
        .folder::before {
            content: "📁";
            display: inline-block;
            transition: transform 0.2s;
        }
        .folder.expanded::before {
            content: "📂";
        }
        .folder-children {
            display: none;
        }
        .folder.expanded + .folder-children {
            display: block;
        }
        .file::before {
            content: "📄";
        }
        .file-wrapper {
            display: inline-flex;
            align-items: center;
            width: 100%;
            justify-content: space-between;
        }
        .file-info {
            display: inline-flex;
            align-items: center;
        }
        .actions {
            display: inline-flex;
            gap: 8px;
            opacity: 0;
            transition: opacity 0.2s;
        }
        .file-wrapper:hover .actions {
            opacity: 1;
        }
        .btn {
            background: #edf2f7;
            border: 1px solid var(--border-color);
            padding: 3px 10px;
            font-size: 0.75rem;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
            color: var(--text-color);
        }
        .btn:hover {
            background: var(--primary-color);
            color: white;
            border-color: var(--primary-color);
        }
        #preview-container {
            margin-top: 20px;
            width: 100%;
            max-width: 900px;
            display: none;
            background: #1e1e1e;
            color: #d4d4d4;
            border-radius: 8px;
            padding: 15px;
            box-sizing: border-box;
        }
        #preview-header {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #333;            padding-bottom: 8px;
            margin-bottom: 10px;
            font-size: 0.9rem;
            align-items: center;
        }
        #preview-content {
            white-space: pre;
            overflow-x: auto;
            font-family: "Courier New", Courier, monospace;
            font-size: 0.85rem;
            max-height: 450px;
            margin: 0;
        }
    </style>
</head>
<body>
<div class="container">
    <h2>📡 IPTV 私库静态大表 (Pages 强力驱动)</h2>
    <div id="file-tree" class="tree-root">正在加载云端快照账本...</div>
</div>
<div id="preview-container">
    <div id="preview-header">
        <span id="preview-title">文件预览</span>
        <button class="btn" onclick="document.getElementById('preview-container').style.display='none'" style="background:#333;color:#fff;border:none;">关闭</button>
    </div>
    <pre id="preview-content"></pre>
</div>
<script>
    const HOST_URL = window.location.origin;
    function buildTree(paths) {
        const root = { name: "root", type: "folder", children: {} };
        paths.forEach(path => {
            const parts = path.split('/');
            let current = root;
            parts.forEach((part, index) => {
                if (index === parts.length - 1) {
                    current.children[part] = { name: part, type: "file", fullPath: path };
                } else {
                    if (!current.children[part]) {
                        current.children[part] = { name: part, type: "folder", children: {} };
                    }
                    current = current.children[part];                }
            });
        });
        return root;
    }
    function renderTree(node, container) {
        const ul = document.createElement('ul');
        ul.className = 'tree-node';
        const sortedKeys = Object.keys(node.children).sort((a, b) => {
            if (node.children[a].type === node.children[b].type) return a.localeCompare(b);
            return node.children[a].type === 'folder' ? -1 : 1;
        });
        sortedKeys.forEach(key => {
            const item = node.children[key];
            const li = document.createElement('li');
            if (item.type === 'folder') {
                const folderSpan = document.createElement('span');
                folderSpan.className = 'folder';
                folderSpan.innerText = item.name;
                folderSpan.onclick = function(e) {
                    e.stopPropagation();
                    this.classList.toggle('expanded');
                };
                li.appendChild(folderSpan);
                const childrenContainer = document.createElement('div');
                childrenContainer.className = 'folder-children';
                renderTree(item, childrenContainer);
                li.appendChild(childrenContainer);
            } else {
                const fileWrapper = document.createElement('div');
                fileWrapper.className = 'file-wrapper';
                const fileInfo = document.createElement('div');
                fileInfo.className = 'file-info';
                const fileSpan = document.createElement('span');
                fileSpan.className = 'file';
                fileSpan.innerText = item.name;
                fileSpan.onclick = () => previewFile(item.fullPath);
                fileInfo.appendChild(fileSpan);
                fileWrapper.appendChild(fileInfo);
                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'actions';
                const fileUrl = HOST_URL + '/' + item.fullPath;
                actionsDiv.innerHTML = `
                    <button class="btn" onclick="navigator.clipboard.writeText('${fileUrl}');alert('订阅地址复制成功！')">📋 复制链接</button>
                    <a class="btn" href="${fileUrl}" target="_blank">🌐 独立打开</a>
                `;
                fileWrapper.appendChild(actionsDiv);
                li.appendChild(fileWrapper);
            }
            ul.appendChild(li);
        });
        container.appendChild(ul);
    }
    async function previewFile(fullPath) {
        const previewContainer = document.getElementById('preview-container');
        const previewTitle = document.getElementById('preview-title');
        const previewContent = document.getElementById('preview-content');
        previewTitle.innerText = "📄 正在预览: " + fullPath;
        previewContent.innerText = "正在加载内容...";
        previewContainer.style.display = 'block';
        try {
            const res = await fetch(HOST_URL + '/' + fullPath);
            const text = await res.text();
            previewContent.innerText = text;
        } catch (e) {
            previewContent.innerText = "❌ 读取内容失败: " + e.message;        }
    }
    async function init() {
        const treeContainer = document.getElementById('file-tree');
        try {
            const response = await fetch(HOST_URL + '/snapshot.json?t=' + new Date().getTime());
            if (!response.ok) throw new Error("无法读取 snapshot.json 快照账本");
            const rawKeys = await response.json();
            treeContainer.innerText = "";
            if (!rawKeys || rawKeys.length === 0) {
                treeContainer.innerText = "⚠️ 空间内没有任何有效数据。";
                return;
            }
            const treeData = buildTree(rawKeys);
            renderTree(treeData, treeContainer);
        } catch (err) {
            treeContainer.innerHTML = `<span style="color:red;">❌ 加载账本失败: ${err.message}</span>`;        }
    }
    window.onload = init;
</script>
</body>
</html>
"""

    try:
        # 🎯 核心修正点：将未定义的 OUTPUT_HTML 纠正为上方配置好的 OUTPUT_INDEX
        with open(OUTPUT_INDEX, "w", encoding="utf-8") as f_html:
            f_html.write(html_content)
        print("🌐 完美控制台静态页面已同步成功写入到私库根目录 index.html ！")
    except Exception as e:
        print(f"❌ 写入 index.html 失败: {e}")

if __name__ == "__main__":
    generate_snapshot_and_portal()
