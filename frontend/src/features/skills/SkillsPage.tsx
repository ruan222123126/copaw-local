import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "../../api/client";
import type { SkillSpec } from "../../api/types";
import "./skills.css";

const sortSkills = (items: SkillSpec[]): SkillSpec[] =>
  [...items].sort((a, b) => a.name.localeCompare(b.name));

const buildSkillContent = (
  name: string,
  description: string,
  instructions: string,
): string => `---
name: ${name}
description: ${description}
---
${instructions.trim() || "在此填写技能说明。"}
`;

export function SkillsPage() {
  const [skills, setSkills] = useState<SkillSpec[]>([]);
  const [loading, setLoading] = useState(true);
  const [busySkillName, setBusySkillName] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newInstructions, setNewInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadSkills = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const data = await apiClient.listSkills();
      setSkills(sortSkills(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载 Skills 失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSkills();
  }, [loadSkills]);

  const enabledCount = useMemo(
    () => skills.filter((skill) => skill.enabled).length,
    [skills],
  );

  const toggleSkill = useCallback(
    async (skill: SkillSpec) => {
      setBusySkillName(skill.name);
      setError(null);
      setNotice(null);
      try {
        if (skill.enabled) {
          await apiClient.disableSkill(skill.name);
        } else {
          await apiClient.enableSkill(skill.name);
        }
        await loadSkills();
      } catch (err) {
        setError(err instanceof Error ? err.message : "更新 Skill 状态失败");
      } finally {
        setBusySkillName(null);
      }
    },
    [loadSkills],
  );

  const removeSkill = useCallback(
    async (skill: SkillSpec) => {
      if (skill.source !== "customized") {
        setError("仅支持删除 customized 来源的 Skill。");
        return;
      }
      if (!window.confirm(`确认删除 Skill「${skill.name}」？`)) {
        return;
      }
      setBusySkillName(skill.name);
      setError(null);
      setNotice(null);
      try {
        const result = await apiClient.deleteSkill(skill.name);
        if (!result.deleted) {
          setError(`Skill「${skill.name}」删除失败。`);
          return;
        }
        await loadSkills();
      } catch (err) {
        setError(err instanceof Error ? err.message : "删除 Skill 失败");
      } finally {
        setBusySkillName(null);
      }
    },
    [loadSkills],
  );

  const createSkill = useCallback(async () => {
    const name = newName.trim();
    const description = newDescription.trim();
    if (!name || !description) {
      setError("创建 Skill 需要填写名称和描述。");
      return;
    }

    setCreating(true);
    setError(null);
    setNotice(null);
    try {
      const content = buildSkillContent(name, description, newInstructions);
      const result = await apiClient.createSkill({
        name,
        content,
      });
      if (!result.created) {
        setError(
          "Skill 创建失败。请确认名称不冲突，且 SKILL.md 元信息合法。",
        );
        return;
      }
      setNotice(`Skill「${name}」创建成功。`);
      setNewName("");
      setNewDescription("");
      setNewInstructions("");
      await loadSkills();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建 Skill 失败");
    } finally {
      setCreating(false);
    }
  }, [loadSkills, newDescription, newInstructions, newName]);

  if (loading) {
    return <p className="skills-muted">Skills 加载中...</p>;
  }

  return (
    <section className="skills-page">
      <header className="skills-header">
        <div>
          <h2>Skills</h2>
          <p>
            当前共 <strong>{skills.length}</strong> 个技能，已启用{" "}
            <strong>{enabledCount}</strong> 个。
          </p>
        </div>
        <button type="button" onClick={() => void loadSkills()}>
          刷新
        </button>
      </header>

      {error ? <p className="skills-error">{error}</p> : null}
      {notice ? <p className="skills-note">{notice}</p> : null}

      <section className="skills-card">
        <h3>创建 Skill（customized）</h3>
        <div className="skills-create-grid">
          <label>
            名称
            <input
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder="my_skill"
            />
          </label>
          <label>
            描述
            <input
              value={newDescription}
              onChange={(event) => setNewDescription(event.target.value)}
              placeholder="一句话描述该 skill"
            />
          </label>
          <label className="full">
            指令正文
            <textarea
              value={newInstructions}
              onChange={(event) => setNewInstructions(event.target.value)}
              placeholder="填写 SKILL.md 正文内容"
              rows={6}
            />
          </label>
        </div>
        <div className="skills-actions">
          <button
            type="button"
            onClick={() => void createSkill()}
            disabled={creating}
          >
            {creating ? "创建中..." : "创建 Skill"}
          </button>
        </div>
      </section>

      <section className="skills-card">
        <h3>技能列表</h3>
        <div className="skills-list">
          {skills.map((skill) => (
            <article className="skills-item" key={skill.name}>
              <div>
                <h4>{skill.name}</h4>
                <p>
                  source: <code>{skill.source}</code> | path:{" "}
                  <code>{skill.path}</code>
                </p>
              </div>
              <div className="skills-item-actions">
                <span className={skill.enabled ? "on" : "off"}>
                  {skill.enabled ? "已启用" : "未启用"}
                </span>
                <button
                  type="button"
                  onClick={() => void toggleSkill(skill)}
                  disabled={busySkillName === skill.name}
                >
                  {skill.enabled ? "停用" : "启用"}
                </button>
                <button
                  type="button"
                  className="danger"
                  onClick={() => void removeSkill(skill)}
                  disabled={
                    skill.source !== "customized" || busySkillName === skill.name
                  }
                >
                  删除
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
