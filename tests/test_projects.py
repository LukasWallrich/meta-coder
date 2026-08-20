from meta_coder.projects import clear_output, create_project, project_archive_files


def test_clear_output_removes_generated_files_but_keeps_inputs(tmp_path):
    project = create_project("t", root=tmp_path)
    (project.raw_dir / "paper.json").write_text("{}", encoding="utf-8")
    (project.output_dir / "coded_data.csv").write_text("row_id\n", encoding="utf-8")
    (project.sources_dir / "paper.pdf").write_text("%PDF-1.4", encoding="utf-8")

    clear_output(project)

    assert not (project.output_dir / "coded_data.csv").exists()
    assert list(project.raw_dir.iterdir()) == []
    assert (project.sources_dir / "paper.pdf").is_file()  # untouched
    assert project.manual_path.is_file()  # untouched


def test_project_archive_files_excludes_internal_metadata(tmp_path):
    project = create_project("t", root=tmp_path)
    (project.sources_dir / "paper.pdf").write_text("%PDF-1.4", encoding="utf-8")

    files = project_archive_files(project)
    arcnames = {arcname for _, arcname in files}

    assert "coding_manual.yml" in arcnames
    assert "coding_sheet.csv" in arcnames
    assert "sources/paper.pdf" in arcnames
    assert not any(name.startswith(".meta_coder") for name in arcnames)
    for abs_path, _ in files:
        assert abs_path.is_file()
