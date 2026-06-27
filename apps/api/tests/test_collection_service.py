from app.services.collection_service import CollectionService


def test_create_collection_does_not_infer_metadata_from_name(
    temp_workspace,
    reset_settings_cache,
) -> None:
    created = CollectionService().create("广东省2022年农村统计年鉴")

    assert created.name == "广东省2022年农村统计年鉴"
    assert not hasattr(created, "source_region")
    assert not hasattr(created, "source_year")
    assert not hasattr(created, "source_type")
    assert not hasattr(created, "source_scope")


def test_create_collection_accepts_explicit_metadata(
    temp_workspace,
    reset_settings_cache,
) -> None:
    created = CollectionService().create(
        "资料集",
        tags=["财务", "财务", ""],
        metadata={"owner": "数据组", "empty": "", "nested": {"ignored": True}},
    )

    assert created.tags == ["财务"]
    assert created.metadata == {"owner": "数据组"}


def test_update_collection_does_not_infer_metadata_from_name(
    temp_workspace,
    reset_settings_cache,
) -> None:
    service = CollectionService()
    created = service.create("原始资料")

    updated = service.update(created.id, "2024销售台账")

    assert updated.name == "2024销售台账"
    assert not hasattr(updated, "source_region")
    assert not hasattr(updated, "source_year")
    assert not hasattr(updated, "source_type")
    assert not hasattr(updated, "source_scope")
