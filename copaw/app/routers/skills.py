# -*- coding: utf-8 -*-
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ...agents.skills_manager import (
    SkillService,
    SkillInfo,
    list_available_skills,
)


class SkillSpec(SkillInfo):
    enabled: bool = False


class CreateSkillRequest(BaseModel):
    name: str = Field(..., description="Skill name")
    content: str = Field(..., description="Skill content (SKILL.md)")
    references: dict[str, Any] | None = Field(
        None,
        description="Optional tree structure for references/. "
        "Can be flat {filename: content} or nested "
        "{dirname: {filename: content}}",
    )
    scripts: dict[str, Any] | None = Field(
        None,
        description="Optional tree structure for scripts/. "
        "Can be flat {filename: content} or nested "
        "{dirname: {filename: content}}",
    )


router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills() -> list[SkillSpec]:
    all_skills = SkillService.list_all_skills()

    available_skills = list_available_skills()
    skills_spec = []
    for skill in all_skills:
        skills_spec.append(
            SkillSpec(
                name=skill.name,
                content=skill.content,
                source=skill.source,
                path=skill.path,
                references=skill.references,
                scripts=skill.scripts,
                enabled=skill.name in available_skills,
            ),
        )
    return skills_spec


@router.get("/available")
async def get_available_skills() -> list[SkillSpec]:
    available_skills = SkillService.list_available_skills()
    skills_spec = []
    for skill in available_skills:
        skills_spec.append(
            SkillSpec(
                name=skill.name,
                content=skill.content,
                source=skill.source,
                path=skill.path,
                references=skill.references,
                scripts=skill.scripts,
                enabled=True,
            ),
        )
    return skills_spec


@router.post("/batch-disable")
async def batch_disable_skills(skill_name: list[str]) -> None:
    for skill in skill_name:
        SkillService.disable_skill(skill)


@router.post("/batch-enable")
async def batch_enable_skills(skill_name: list[str]) -> None:
    for skill in skill_name:
        SkillService.enable_skill(skill)


@router.post("")
async def create_skill(request: CreateSkillRequest):
    result = SkillService.create_skill(
        name=request.name,
        content=request.content,
        references=request.references,
        scripts=request.scripts,
    )
    return {"created": result}


@router.post("/{skill_name}/disable")
async def disable_skill(skill_name: str):
    result = SkillService.disable_skill(skill_name)
    return {"disabled": result}


@router.post("/{skill_name}/enable")
async def enable_skill(skill_name: str):
    result = SkillService.enable_skill(skill_name)
    return {"enabled": result}


@router.delete("/{skill_name}")
async def delete_skill(skill_name: str):
    """Delete a skill from customized_skills directory permanently.

    This only deletes skills from customized_skills directory.
    Built-in skills cannot be deleted.
    """
    result = SkillService.delete_skill(skill_name)
    return {"deleted": result}


@router.get("/{skill_name}/files/{source}/{file_path:path}")
async def load_skill_file(
    skill_name: str,
    source: str,
    file_path: str,
):
    """Load a specific file from a skill's references or scripts directory.

    Args:
        skill_name: Name of the skill
        source: Source directory ("builtin" or "customized")
        file_path: Path relative to skill directory, must start with
                   "references/" or "scripts/"

    Returns:
        File content as string, or None if not found

    Example:
        GET /skills/my_skill/files/customized/references/doc.md
        GET /skills/builtin_skill/files/builtin/scripts/utils/helper.py
    """
    content = SkillService.load_skill_file(
        skill_name=skill_name,
        file_path=file_path,
        source=source,
    )
    return {"content": content}
