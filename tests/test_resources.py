from aia_portal.repository import DEFAULT_RESOURCES, DemoRepository


def test_default_published_resources_are_actionable():
    for resource in DEFAULT_RESOURCES:
        if resource["status"] == "published":
            assert resource.get("external_url") or resource.get("content")


def test_demo_resource_content_is_preserved():
    resources = DemoRepository({}).resources()
    methodology = next(item for item in resources if item["resource_type"] == "Methodology")
    assert "Review process" in methodology["content"]
