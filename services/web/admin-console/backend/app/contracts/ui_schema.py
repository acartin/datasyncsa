from pydantic import BaseModel
from typing import List, Optional, Literal

class UIComponent(BaseModel):
    type: str
    label: Optional[str] = None
    color: Optional[str] = "primary" # Relaxed literal for now or keep it strict? Keeping strict might break valid Velzon tokens if not listed. Let's make it optional string for flexibility.
    
    # Generic fields for various components
    components: Optional[List['UIComponent']] = None # Recursive for Grid
    text: Optional[str] = None # For Typography
    tag: Optional[str] = None # For Typography
    buttons: Optional[List[dict]] = None # For Button Group
    class_: Optional[str] = None # For custom classes (using class_ alias for 'class')

    properties: dict = {}

    model_config = {
        "extra": "allow", # Allow arbitrary fields like 'icon', 'metric', etc.
        "populate_by_name": True
    }

class UIMenuItem(BaseModel):
    id: str
    label: str
    icon: Optional[str] = None
    link: Optional[str] = None # For navigation
    subItems: Optional[List['UIMenuItem']] = None # Recursive submenu

class UISidebar(BaseModel):
    brand: str
    items: List[UIMenuItem]

class UIAppShell(BaseModel):
    layout: Literal["dashboard-shell"] = "dashboard-shell"
    sidebar: UISidebar
    content: List['UIComponent'] # Initial content to load

class WebIAFirstResponse(BaseModel):
    # This might be deprecated or used for partial updates, but for app-init we'll use UIAppShell
    layout: str
    components: Optional[List[UIComponent]] = None
    properties: Optional[dict] = None
    tabs: Optional[List[dict]] = None
