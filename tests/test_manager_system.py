import asyncio

from jarvis.managers import ManagerRequest, ManagerSystem


def test_default_managers_exist():
    system = ManagerSystem()
    names = {item["name"] for item in system.list_managers()}
    assert names == {"system", "files", "3d", "projects", "communications", "security", "memory"}


def test_routes_blender_to_3d_manager():
    system = ManagerSystem()
    assert system.route(ManagerRequest("Open Blender and modify the 3D model")).name == "3d"


def test_routes_approved_files_to_file_manager():
    system = ManagerSystem()
    assert system.route(ManagerRequest("Open this approved project file")).name == "files"


def test_routes_email_to_communications_manager():
    system = ManagerSystem()
    assert system.route(ManagerRequest("Draft an email reply")).name == "communications"


def test_unknown_request_falls_back_to_system():
    system = ManagerSystem()
    assert system.route(ManagerRequest("do the thing")).name == "system"


def test_dispatch_returns_selected_manager():
    system = ManagerSystem()
    result = asyncio.run(system.dispatch(ManagerRequest("remember this project detail")))
    assert result["manager"] == "memory"
    assert result["status"] == "routed"
