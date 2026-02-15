import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "../../api/client";
import type { MdFileInfo } from "../../api/types";
import "./workspace.css";

type FileScope = "working" | "memory";

const sortMdFiles = (items: MdFileInfo[]): MdFileInfo[] =>
  [...items].sort(
    (a, b) =>
      new Date(b.modified_time).getTime() - new Date(a.modified_time).getTime(),
  );

export function WorkspacePage() {
  const [scope, setScope] = useState<FileScope>("working");
  const [files, setFiles] = useState<MdFileInfo[]>([]);
  const [selectedFile, setSelectedFile] = useState("");
  const [content, setContent] = useState("");
  const [newFileName, setNewFileName] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingContent, setLoadingContent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshFileList = useCallback(
    async (targetScope: FileScope, preferredFileName?: string) => {
      setLoadingList(true);
      setError(null);
      setNotice(null);
      try {
        const list =
          targetScope === "working"
            ? await apiClient.listWorkingFiles()
            : await apiClient.listMemoryFiles();
        const sorted = sortMdFiles(list);
        setFiles(sorted);
        setSelectedFile((current) => {
          const candidate = preferredFileName ?? current;
          if (candidate && sorted.some((file) => file.filename === candidate)) {
            return candidate;
          }
          return sorted[0]?.filename ?? "";
        });
        if (sorted.length === 0) {
          setContent("");
          setDirty(false);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载工作区文件失败");
      } finally {
        setLoadingList(false);
      }
    },
    [],
  );

  useEffect(() => {
    void refreshFileList(scope);
  }, [scope, refreshFileList]);

  const loadFileContent = useCallback(async (targetScope: FileScope, name: string) => {
    setLoadingContent(true);
    setError(null);
    try {
      const result =
        targetScope === "working"
          ? await apiClient.loadWorkingFile(name)
          : await apiClient.loadMemoryFile(name);
      setContent(result.content);
      setDirty(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "读取文件内容失败");
    } finally {
      setLoadingContent(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedFile) {
      setContent("");
      setDirty(false);
      return;
    }
    void loadFileContent(scope, selectedFile);
  }, [loadFileContent, scope, selectedFile]);

  const selectedMeta = useMemo(
    () => files.find((file) => file.filename === selectedFile) ?? null,
    [files, selectedFile],
  );

  const selectFile = useCallback(
    (name: string) => {
      if (dirty && name !== selectedFile) {
        const confirmed = window.confirm("当前文件有未保存改动，确认切换吗？");
        if (!confirmed) {
          return;
        }
      }
      setSelectedFile(name);
    },
    [dirty, selectedFile],
  );

  const switchScope = useCallback(
    (next: FileScope) => {
      if (next === scope) {
        return;
      }
      if (dirty) {
        const confirmed = window.confirm("当前文件有未保存改动，确认切换分组吗？");
        if (!confirmed) {
          return;
        }
      }
      setScope(next);
      setSelectedFile("");
      setContent("");
      setDirty(false);
    },
    [dirty, scope],
  );

  const saveCurrentFile = useCallback(async () => {
    if (!selectedFile) {
      setError("请先选择一个文件。");
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      if (scope === "working") {
        await apiClient.saveWorkingFile(selectedFile, content);
      } else {
        await apiClient.saveMemoryFile(selectedFile, content);
      }
      setDirty(false);
      setNotice(`文件「${selectedFile}」已保存。`);
      await refreshFileList(scope, selectedFile);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存文件失败");
    } finally {
      setSaving(false);
    }
  }, [content, refreshFileList, scope, selectedFile]);

  const createFile = useCallback(async () => {
    const rawName = newFileName.trim();
    if (!rawName) {
      setError("请输入文件名。");
      return;
    }
    const normalizedName = rawName.endsWith(".md") ? rawName : `${rawName}.md`;

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      if (scope === "working") {
        await apiClient.saveWorkingFile(normalizedName, "");
      } else {
        await apiClient.saveMemoryFile(normalizedName, "");
      }
      setNewFileName("");
      setNotice(`文件「${normalizedName}」创建成功。`);
      await refreshFileList(scope, normalizedName);
      setSelectedFile(normalizedName);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建文件失败");
    } finally {
      setSaving(false);
    }
  }, [newFileName, refreshFileList, scope]);

  if (loadingList) {
    return <p className="workspace-muted">Workspace 加载中...</p>;
  }

  return (
    <section className="workspace-page">
      <header className="workspace-header">
        <div>
          <h2>Workspace</h2>
          <p>查看并编辑工作区 Markdown 文件（working / memory）。</p>
        </div>
        <div className="workspace-actions">
          <button type="button" onClick={() => void refreshFileList(scope)}>
            刷新
          </button>
          <button
            type="button"
            onClick={() => void saveCurrentFile()}
            disabled={!selectedFile || saving}
          >
            {saving ? "处理中..." : "保存当前文件"}
          </button>
        </div>
      </header>

      {error ? <p className="workspace-error">{error}</p> : null}
      {notice ? <p className="workspace-note">{notice}</p> : null}

      <div className="workspace-tabs">
        <button
          type="button"
          className={scope === "working" ? "active" : ""}
          onClick={() => switchScope("working")}
        >
          working
        </button>
        <button
          type="button"
          className={scope === "memory" ? "active" : ""}
          onClick={() => switchScope("memory")}
        >
          memory
        </button>
      </div>

      <div className="workspace-grid">
        <aside className="workspace-files">
          <div className="workspace-new-file">
            <input
              value={newFileName}
              onChange={(event) => setNewFileName(event.target.value)}
              placeholder="new-file.md"
            />
            <button type="button" onClick={() => void createFile()} disabled={saving}>
              新建
            </button>
          </div>
          <ul>
            {files.map((file) => (
              <li key={file.filename}>
                <button
                  type="button"
                  className={selectedFile === file.filename ? "active" : ""}
                  onClick={() => selectFile(file.filename)}
                >
                  <strong>{file.filename}</strong>
                  <span>{new Date(file.modified_time).toLocaleString()}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="workspace-editor">
          <header>
            <h3>{selectedFile || "未选择文件"}</h3>
            {selectedMeta ? (
              <p>
                size: {selectedMeta.size} bytes | modified:{" "}
                {new Date(selectedMeta.modified_time).toLocaleString()}
              </p>
            ) : null}
          </header>
          <textarea
            value={content}
            onChange={(event) => {
              setContent(event.target.value);
              setDirty(true);
            }}
            placeholder="选择文件后开始编辑..."
            disabled={!selectedFile || loadingContent}
          />
        </section>
      </div>
    </section>
  );
}
