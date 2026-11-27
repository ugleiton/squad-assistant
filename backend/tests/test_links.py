from app.gitlab.links import find_mr_links, matches_project


def test_finds_mr_link_in_slack_text():
    text = "Pode revisar? <https://gitlab.example.com/team/sub/app/-/merge_requests/42|MR 42>"
    [link] = find_mr_links(text)
    assert link.project == "team/sub/app"
    assert link.iid == 42
    assert link.host == "gitlab.example.com"


def test_project_filter():
    [link] = find_mr_links("https://gitlab.com/g/app/-/merge_requests/1")
    assert matches_project(link, [])
    assert matches_project(link, ["G/App"])
    assert not matches_project(link, ["g/other"])
