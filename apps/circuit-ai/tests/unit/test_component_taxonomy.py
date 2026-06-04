from src.vision.component_taxonomy import normalize_component_class_name


def test_component_taxonomy_normalizes_external_model_labels():
    assert normalize_component_class_name("ic") == "ic_chip"
    assert normalize_component_class_name("clock") == "crystal"
    assert normalize_component_class_name("Resestor") == "resistor"
