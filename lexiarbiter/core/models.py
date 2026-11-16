"""Core data models: Annotation and Document."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Annotation:
    """A single annotation span on the document.

    `labels` is a mapping from group_id (e.g. "argument_type") to label_id
    (e.g. "major_premise"). A span may have labels from one, several, or all
    groups defined in the active annotation mode (partial annotation is OK).
    """

    start: int
    end: int
    labels: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    note: str = ""
    concept_id: Optional[str] = None  # 新增：關聯的概念 ID
    explanation_start: Optional[int] = None
    explanation_end: Optional[int] = None
    broader_concept_id: Optional[str] = None
    explanation_text: str = ""
    broader_concept_ids: list[str] = field(default_factory=list)

    def __post_init__(self):
        # 舊版 .lexa 只有單一 broader_concept_id；載入時自動升級成清單。
        if self.broader_concept_ids:
            self.set_broader_concept_ids(self.broader_concept_ids)
        elif self.broader_concept_id:
            self.broader_concept_ids = [self.broader_concept_id]

    def set_broader_concept_ids(self, concept_ids: list[str]) -> None:
        """設定多個上位概念，並同步維持舊版單一欄位的相容性。"""
        self.broader_concept_ids = list(dict.fromkeys(
            concept_id for concept_id in concept_ids if concept_id
        ))
        self.broader_concept_id = (
            self.broader_concept_ids[0]
            if self.broader_concept_ids
            else None
        )

    def get_broader_concept_ids(self) -> list[str]:
        """回傳上位概念清單，並相容執行期間仍設定舊欄位的程式碼。"""
        if self.broader_concept_ids:
            return list(self.broader_concept_ids)
        return [self.broader_concept_id] if self.broader_concept_id else []

    def overlaps(self, other: "Annotation") -> bool:
        return not (self.end <= other.start or other.end <= self.start)

    def contains(self, pos: int) -> bool:
        return self.start <= pos < self.end

    def to_dict(self) -> dict:
        data = asdict(self)
        broader_ids = self.get_broader_concept_ids()
        data["broader_concept_ids"] = broader_ids
        # 舊版工具仍可讀到第一個上位概念。
        data["broader_concept_id"] = broader_ids[0] if broader_ids else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Annotation":
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            start=int(data["start"]),
            end=int(data["end"]),
            labels=dict(data.get("labels", {})),
            note=data.get("note", ""),
            concept_id=data.get("concept_id"),  # 讀取概念 ID
            explanation_start=data.get("explanation_start"),
            explanation_end=data.get("explanation_end"),
            broader_concept_id=(
                (
                    data.get("broader_concept_ids")[0]
                    if isinstance(data.get("broader_concept_ids"), list)
                    and data.get("broader_concept_ids")
                    else data.get("broader_concept_ids")
                    if isinstance(data.get("broader_concept_ids"), str)
                    else None
                )
                if "broader_concept_ids" in data
                else data.get("broader_concept_id")
            ),
            explanation_text=data.get("explanation_text", ""),
            broader_concept_ids=(
                (
                    [data.get("broader_concept_ids")]
                    if isinstance(data.get("broader_concept_ids"), str)
                    else list(data.get("broader_concept_ids") or [])
                )
                if "broader_concept_ids" in data
                else ([data["broader_concept_id"]]
                      if data.get("broader_concept_id") else [])
            ),
        )


@dataclass
class Document:
    """In-memory representation of a document being annotated."""

    text: str
    annotations: list[Annotation] = field(default_factory=list)
    schema_id: str = ""
    source_filename: str = ""
    source_meta: dict = field(default_factory=dict)
    concepts: dict[str, str] = field(default_factory=dict)  # 新增：全域概念池 {concept_id: concept_name}
    file_path: Optional[str] = None  # path of the loaded .json or .lexa
    dirty: bool = False

    # ------------------------------------------------------------------
    # Annotation management

    def add_annotation(self, ann: Annotation) -> None:
        self.annotations.append(ann)
        self.dirty = True

    def remove_annotation(self, ann_id: str) -> bool:
        before = len(self.annotations)
        self.annotations = [a for a in self.annotations if a.id != ann_id]
        if len(self.annotations) != before:
            self.dirty = True
            return True
        return False

    def find_annotation(self, ann_id: str) -> Optional[Annotation]:
        for a in self.annotations:
            if a.id == ann_id:
                return a
        return None

    def annotations_at(self, pos: int) -> list[Annotation]:
        """All annotations covering a given character position."""
        return [a for a in self.annotations if a.contains(pos)]

    def annotations_in_range(self, start: int, end: int) -> list[Annotation]:
        return [
            a for a in self.annotations
            if not (a.end <= start or end <= a.start)
        ]

    def annotations_in_range_for_group(
        self, start: int, end: int, group_id: str
    ) -> list[Annotation]:

        result = []

        for a in self.annotations:      
            # TODO: 完成以下缺失的部份
            # 請判斷既有標註是否與使用者選取的範圍 (start, end) 有重疊？
            # 如果有重疊，請將 is_overlapping 設為 True；否則為 False。

            is_overlapping = not(a.end<=start or end<=a.start)  # <--- 請修改這行的邏輯

            # ==========================================================

            has_group = (group_id in a.labels)

            if is_overlapping and has_group:
                result.append(a)

        # 把收集到的所有衝突標註回傳出去
        return result
         

    def sorted_annotations(self) -> list[Annotation]:
        return sorted(self.annotations, key=lambda a: (a.start, a.end))


def detect_same_group_conflicts(
    annotations: list[Annotation],
) -> list[tuple[int, int, str, list[str]]]:
    """掃出同一字元範圍內、同群組卻有多個不同 label 的衝突段。

    回傳 ``[(start, end, group_id, [label_ids])...]``，每筆對應一段不可分割
    的衝突區段。``label_ids`` 依「被加入 seg_labels 的順序」排列，與
    :func:`lexiarbiter.core.io.export_txt` 的「先標註者勝」邏輯一致，讓
    UI 能向使用者解釋實際匯出時哪個 label 會被採用。
    """
    # 收 boundary points（與 export_txt 同套切段邏輯，但這裡只關心衝突）。
    points: set[int] = set()
    for a in annotations:
        points.add(a.start)
        points.add(a.end)
    sorted_points = sorted(points)

    out: list[tuple[int, int, str, list[str]]] = []
    for i in range(len(sorted_points) - 1):
        s, e = sorted_points[i], sorted_points[i + 1]
        if s >= e:
            continue
        # 每個 group 在此段收集所有看過的 label_id（順序、去重）。
        seen: dict[str, list[str]] = {}
        for a in annotations:
            if a.start <= s and e <= a.end:
                for gid, lid in a.labels.items():
                    lst = seen.setdefault(gid, [])
                    if lid not in lst:
                        lst.append(lid)
        for gid, lids in seen.items():
            if len(lids) > 1:
                out.append((s, e, gid, lids))
    return out
