from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class AssignmentData:
    id: str
    portal: str
    course_name: str
    title: str
    description: str
    due_date: str
    raw_html: Optional[str] = None
    attachments: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "portal": self.portal,
            "course_name": self.course_name,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date,
            "attachments": self.attachments
        }

class BaseSLCMAdapter(ABC):
    @abstractmethod
    def login(self) -> bool:
        """Autentikasi ke portal kampus / SSO"""
        pass

    @abstractmethod
    def fetch_active_assignments(self) -> List[AssignmentData]:
        """Ambil daftar seluruh tugas aktif dari portal kampus"""
        pass

    @abstractmethod
    def fetch_assignment_details(self, task_id: str) -> Optional[AssignmentData]:
        """Ambil detail instruksi lengkap dari tugas tertentu"""
        pass
