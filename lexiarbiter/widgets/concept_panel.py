"""Concept management UI components."""
import uuid
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QTreeWidget, QTreeWidgetItem, QMenu,
    QAbstractItemView, QLineEdit, QPushButton,
    QLabel, QWidget, QMessageBox
)

class ConceptSelectionDialog(QDialog):
    """彈出視窗：讓使用者從現有概念挑選，或輸入新概念。"""
    def __init__(
        self,
        concepts: dict[str, str],
        default_text: str = "",
        parent=None,
        allow_new: bool = True,
        broader_by_concept: dict[str, str] | None = None,
    ):
        super().__init__(parent)
        self.allow_new = allow_new
        self._updating_tree = False
        self.setWindowTitle("選擇或新增對應概念")
        self.resize(420, 500)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("1. 從概念階層中選擇："))
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        self._concept_map = {
            name: cid for cid, name in concepts.items()
        }
        self._tree_items: dict[str, QTreeWidgetItem] = {}
        self._build_concept_tree(
            concepts,
            broader_by_concept or {},
        )
        self.tree_widget.expandAll()
        layout.addWidget(self.tree_widget)

        self.input_label = QLabel("2. 或直接輸入新概念：")
        layout.addWidget(self.input_label)
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("輸入新術語概念...")
        # 自動將反白的文字填入輸入框
        self.input_edit.setText(default_text) 
        # 選取框內所有文字，方便使用者如果不滿意可以直接打字覆蓋
        self.input_edit.selectAll()
        layout.addWidget(self.input_edit)

        # 有些流程（例如「要被設定的子概念」）只能選既有概念。
        # 直接隱藏新增欄位，避免使用者輸入後才收到拒絕訊息。
        self.input_label.setVisible(allow_new)
        self.input_edit.setVisible(allow_new)

        # 按鈕區
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("確定 (Enter)")
        self.btn_ok.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setStyleSheet("background-color: #546E7A; color: white; padding: 6px; border-radius: 4px;")
        self.btn_cancel.clicked.connect(self.reject)

        # 將按鈕推到對話框的右下角
        btn_layout.addStretch()
        
        # 將 OK 放在前面 (左邊)，Cancel 放在後面 (右邊)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # 階層清單採單選勾選；點文字或方框都會選取該概念。
        self.tree_widget.itemClicked.connect(
            self._on_tree_item_clicked
        )
        self.tree_widget.itemChanged.connect(
            self._on_tree_item_changed
        )
        self.tree_widget.itemDoubleClicked.connect(
            lambda _item, _column: self.accept()
        )
        self.input_edit.textEdited.connect(
            self._on_input_edited
        )

    def _build_concept_tree(
        self,
        concepts: dict[str, str],
        broader_by_concept: dict[str, str | list[str]],
    ):
        """依 concept -> broader concepts 關係建立可展開的概念樹。"""
        all_parents: dict[str, list[str]] = {}
        for child_id, raw_parent_ids in broader_by_concept.items():
            if isinstance(raw_parent_ids, str):
                raw_parent_ids = [raw_parent_ids]
            parent_ids = [
                parent_id
                for parent_id in raw_parent_ids
                if parent_id in concepts and parent_id != child_id
            ]
            if child_id in concepts and parent_ids:
                all_parents[child_id] = list(dict.fromkeys(parent_ids))

        # 選目標概念時以第一個上位概念呈現階層；完整的上位概念集合仍會顯示在提示文字。
        parent_by_child = {
            child_id: parent_ids[0]
            for child_id, parent_ids in all_parents.items()
        }

        # 防止舊資料中的循環關係讓概念完全無法顯示；遇到循環時，
        # 將其中一個節點提升為根節點。
        for concept_id in list(parent_by_child):
            seen = {concept_id}
            current = parent_by_child.get(concept_id)
            while current is not None:
                if current in seen:
                    parent_by_child.pop(concept_id, None)
                    break
                seen.add(current)
                current = parent_by_child.get(current)

        children_by_parent: dict[str, list[str]] = {}
        for child_id, parent_id in parent_by_child.items():
            children_by_parent.setdefault(parent_id, []).append(
                child_id
            )

        def add_item(
            concept_id: str,
            parent_item: QTreeWidgetItem | None,
        ):
            item = QTreeWidgetItem([concepts[concept_id]])
            item.setData(0, Qt.UserRole, concept_id)
            item.setFlags(
                item.flags()
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsSelectable
                | Qt.ItemIsEnabled
            )
            item.setCheckState(0, Qt.Unchecked)

            parent_ids = all_parents.get(concept_id, [])
            if not parent_ids:
                item.setToolTip(0, "最上層概念")
            else:
                item.setToolTip(
                    0,
                    "上位概念：" + "、".join(
                        concepts[parent_id] for parent_id in parent_ids
                    ),
                )

            if parent_item is None:
                self.tree_widget.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            self._tree_items[concept_id] = item

            child_ids = children_by_parent.get(concept_id, [])
            for child_id in sorted(
                child_ids,
                key=lambda cid: concepts[cid],
            ):
                add_item(child_id, item)

        root_ids = [
            concept_id
            for concept_id in concepts
            if concept_id not in parent_by_child
        ]
        for concept_id in sorted(
            root_ids,
            key=lambda cid: concepts[cid],
        ):
            add_item(concept_id, None)

    def _select_tree_item(self, item: QTreeWidgetItem):
        self._updating_tree = True
        try:
            for other in self._tree_items.values():
                other.setCheckState(
                    0,
                    Qt.Checked if other is item else Qt.Unchecked,
                )
            self.tree_widget.setCurrentItem(item)
        finally:
            self._updating_tree = False

        if self.allow_new:
            self.input_edit.setText(item.text(0))

    def _on_tree_item_clicked(
        self,
        item: QTreeWidgetItem,
        _column: int,
    ):
        self._select_tree_item(item)

    def _on_tree_item_changed(
        self,
        item: QTreeWidgetItem,
        _column: int,
    ):
        if self._updating_tree:
            return
        if item.checkState(0) == Qt.Checked:
            self._select_tree_item(item)

    def _on_input_edited(self, text: str):
        """輸入新名稱時取消舊勾選，避免畫面同時表示兩種結果。"""
        if not self.allow_new:
            return
        current = self.tree_widget.currentItem()
        if current is None or text.strip() == current.text(0):
            return
        self._updating_tree = True
        try:
            current.setCheckState(0, Qt.Unchecked)
            self.tree_widget.clearSelection()
        finally:
            self._updating_tree = False

    def accept(self):
        if not self.allow_new:
            if self.tree_widget.currentItem() is None:
                QMessageBox.information(
                    self,
                    "請選擇既有概念",
                    "請從上方清單選擇要設定的概念。",
                )
                self.tree_widget.setFocus()
                return

            super().accept()
            return

        text = self.input_edit.text().strip()

        if not text:
            QMessageBox.information(
                self,
                "概念名稱不可空白",
                "請選擇既有概念，或輸入新的概念名稱。",
            )
            self.input_edit.setFocus()
            return

        super().accept()


    def get_result(self) -> tuple[str | None, str | None]:
        """回傳 (已存在的 ID, 新增的名稱)。若輸入框為空則回傳 (None, None)。"""
        if not self.allow_new:
            item = self.tree_widget.currentItem()
            if item is None:
                return None, None
            return item.data(0, Qt.UserRole), None

        text = self.input_edit.text().strip()
        if not text:
            return None, None
        if text in self._concept_map:
            return self._concept_map[text], None
        return None, text


class BroaderConceptSelectionDialog(QDialog):
    """以勾選清單設定多個上位概念，並可逐項或一次取消選取。"""

    def __init__(
        self,
        concepts: dict[str, str],
        selected_ids: list[str] | None = None,
        parent=None,
        exclusive_id: str | None = None,
        broader_by_concept: dict[str, str | list[str]] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("選擇上位概念")
        self.resize(440, 520)
        self._exclusive_id = exclusive_id
        self._selected_ids = set(selected_ids or [])
        if exclusive_id in self._selected_ids:
            self._selected_ids = {exclusive_id}
        self._updating_items = False
        self._broader_map = broader_by_concept or {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "勾選一個或多個上位概念；點「清除全部」可取消所有選取。"
        ))

        self.list_widget = QListWidget()
        self._items: dict[str, QListWidgetItem] = {}
        for concept_id, name in sorted(
            concepts.items(), key=lambda item: item[1]
        ):
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, concept_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if concept_id in self._selected_ids
                else Qt.Unchecked
            )
            parents = self._normalise_parent_ids(
                self._broader_map.get(concept_id)
            )
            if parents:
                names = [concepts.get(pid, pid) for pid in parents]
                item.setToolTip("目前上位概念：" + "、".join(names))
            else:
                item.setToolTip("目前未設定上位概念")
            self.list_widget.addItem(item)
            self._items[concept_id] = item
        self.list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget, 1)

        selection_buttons = QHBoxLayout()
        self.clear_button = QPushButton("清除勾選")
        self.clear_button.clicked.connect(self.clear_selection)
        selection_buttons.addWidget(self.clear_button)
        selection_buttons.addStretch()
        layout.addLayout(selection_buttons)

        layout.addWidget(QLabel("也可以輸入一個新的上位概念："))
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("輸入新上位概念名稱（可留空）")
        layout.addWidget(self.input_edit)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.btn_ok = QPushButton("確定")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        button_row.addWidget(self.btn_ok)
        button_row.addWidget(self.btn_cancel)
        layout.addLayout(button_row)

    @staticmethod
    def _normalise_parent_ids(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        return [concept_id for concept_id in value if concept_id]

    def _on_item_changed(self, item: QListWidgetItem):
        if self._updating_items:
            return
        concept_id = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            if self._exclusive_id == concept_id:
                self._updating_items = True
                for other_id, other in self._items.items():
                    if other_id != concept_id:
                        other.setCheckState(Qt.Unchecked)
                self._updating_items = False
            elif self._exclusive_id in self._items:
                self._updating_items = True
                self._items[self._exclusive_id].setCheckState(Qt.Unchecked)
                self._updating_items = False

    def clear_selection(self):
        self._updating_items = True
        try:
            for item in self._items.values():
                item.setCheckState(Qt.Unchecked)
        finally:
            self._updating_items = False

    def get_result(self) -> tuple[list[str], str | None]:
        selected_ids = [
            concept_id
            for concept_id, item in self._items.items()
            if item.checkState() == Qt.Checked
        ]
        new_name = self.input_edit.text().strip() or None
        return selected_ids, new_name


class ConceptSidebar(QWidget):
    """側邊欄：顯示當前文件所有的概念池"""
    concept_clicked = Signal(str)
    concept_action = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        title = QLabel("文件概念清單 (Concepts)")
        f = title.font()
        f.setBold(True)
        title.setFont(f)

        tree_controls = QHBoxLayout()
        self.expand_all_button = QPushButton("展開全部")
        self.expand_all_button.clicked.connect(
            lambda: self.list_widget.expandAll()
        )
        self.collapse_all_button = QPushButton("收合全部")
        self.collapse_all_button.clicked.connect(
            lambda: self.list_widget.collapseAll()
        )
        tree_controls.addWidget(self.expand_all_button)
        tree_controls.addWidget(self.collapse_all_button)
        tree_controls.addStretch()
        
        self.list_widget = QTreeWidget()
        self.list_widget.setHeaderHidden(True)
        self.list_widget.setIndentation(20)
        self.list_widget.setItemsExpandable(True)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_menu)
        self.list_widget.itemClicked.connect(
            self._on_item_clicked
        )
        
        layout.addWidget(title)
        layout.addLayout(tree_controls)
        layout.addWidget(self.list_widget)

    def refresh(self, doc):
        self.list_widget.clear()
        if not doc or not hasattr(doc, 'concepts'):
            return
        parent_by_child: dict[str, list[str]] = {}
        for ann in doc.annotations:
            if ann.concept_id not in doc.concepts:
                continue
            parents = parent_by_child.setdefault(ann.concept_id, [])
            for parent_id in ann.get_broader_concept_ids():
                if (
                    parent_id in doc.concepts
                    and parent_id != ann.concept_id
                    and parent_id not in parents
                ):
                    parents.append(parent_id)

        by_parent: dict[str, list[str]] = {}
        for child_id, parent_ids in parent_by_child.items():
            for parent_id in parent_ids:
                by_parent.setdefault(parent_id, []).append(child_id)

        reachable: set[str] = set()

        def add(cid, parent_item=None, ancestors=frozenset()):
            item = QTreeWidgetItem([doc.concepts[cid]])
            item.setData(0, Qt.UserRole, cid)
            parent_names = [
                doc.concepts[parent_id]
                for parent_id in parent_by_child.get(cid, [])
            ]
            item.setToolTip(
                0,
                "上位概念：" + "、".join(parent_names)
                if parent_names else "最上層概念",
            )
            (parent_item.addChild(item) if parent_item else self.list_widget.addTopLevelItem(item))
            reachable.add(cid)
            next_ancestors = ancestors | {cid}
            for child in sorted(by_parent.get(cid, []), key=lambda x: doc.concepts[x]):
                if child not in next_ancestors:
                    add(child, item, next_ancestors)

        roots = [
            cid for cid in doc.concepts
            if not parent_by_child.get(cid)
        ]
        for cid in sorted(roots, key=lambda x: doc.concepts[x]):
            add(cid)

        # 舊檔可能有循環關係，讓尚未顯示的概念仍以根節點出現。
        for cid in sorted(
            (concept_id for concept_id in doc.concepts if concept_id not in reachable),
            key=lambda x: doc.concepts[x],
        ):
            add(cid)

        self.list_widget.expandAll()

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int):
        concept_id = item.data(0, Qt.UserRole)

        if concept_id:
            self.concept_clicked.emit(concept_id)

    def _show_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item is None: return
        cid = item.data(0, Qt.UserRole)
        menu = QMenu(self)
        edit = menu.addAction("編輯概念…")
        delete = menu.addAction("刪除概念")
        chosen = menu.exec(self.list_widget.viewport().mapToGlobal(pos))
        if chosen is edit: self.concept_action.emit(cid, "edit")
        elif chosen is delete: self.concept_action.emit(cid, "delete")
