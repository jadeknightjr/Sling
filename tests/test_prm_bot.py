import pytest
import github3
from unittest.mock import MagicMock

from Sling.chalicelib.prmbot import (
    get_secret,
    get_config,
    has_valid_label,
    has_valid_review,
    get_mergeable_pr,
    merge_pull_req,
)


def test_invalid_config_path():
    with pytest.raises(FileNotFoundError):
        config = get_config("does_not_exist.config")


@pytest.mark.parametrize(
    "config_path, expected_repo, expected_owner",
    [
        ("tests/settings/settings.config", "dumpy", "jadeknightjr"),
        ("tests/settings/test_settings.config", "pearson", "pearsonflynn"),
    ],
)
def test_get_config(config_path, expected_repo, expected_owner):
    config = get_config(config_path)
    repo_name = config["repo_name"]
    repo_owner = config["repo_owner"]

    assert repo_name == expected_repo
    assert repo_owner == expected_owner


@pytest.mark.parametrize(
    "labels, merge_label, expected",
    [
        ([{"name": "bugs"}], "mergeable", False),
        ([{"name": "bugs"}, {"name": "test"}], "mergeable", False),
        ([{"name": "mergeable"}, {"name": "core"}], "mergeable", True),
        ([{"name": "mergeable"}], "mergeable", True),
        ([{"name": "mergeable"}], None, False),
        ([], None, False),
    ],
)
def test_has_valid_label(labels, merge_label, expected):
    assert has_valid_label(labels, merge_label) == expected


@pytest.mark.parametrize(
    "attrib_tuple_list, pr_id, expected",
    [
        ([], "0001", False),
        ([("NONE", "COMMENT")], "0002", False),
        ([("NONE", "APPROVED")], "0003", False),
        ([("COLLABORATOR", "REQUEST_CHANGES"), ("NONE", "APPROVED")], "0004", False),
        ([("MEMBER", "APPROVED")], "0005", True),
        (
            [
                ("MEMBER", "APPROVED"),
                ("COLLABORATOR", "REQUEST_CHANGES"),
                ("COLLABORATOR", "APPROVED"),
            ],
            "0006",
            True,
        ),
    ],
)
def test_has_valid_review(attrib_tuple_list, pr_id, expected):
    reviews = []
    for attrib_tuple in attrib_tuple_list:
        mock = MagicMock(
            spec=github3.pulls.ReviewComment,
            author_association=attrib_tuple[0],
            state=attrib_tuple[1],
        )
        reviews.append(mock)
    assert len(reviews) == len(attrib_tuple_list)
    assert has_valid_review(reviews, pr_id) == expected


@pytest.fixture()
def make_review_list():
    def create_review_list(setup_info):
        pr_generator = []
        for pull_request in setup_info:
            reviews_list = []
            for review_tuple in pull_request["reviews_info"]:
                mock_review = MagicMock(
                    spec=github3.pulls.ReviewComment,
                    author_association=review_tuple[0],
                    state=review_tuple[1],
                )
                reviews_list.append(mock_review)

            mock_pr = MagicMock(
                spec=github3.pulls.ShortPullRequest,
                labels=pull_request["pr_labels"],
                id=pull_request["pr_id"],
            )
            mock_pr.reviews = MagicMock(return_value=reviews_list)

            pr_generator.append(mock_pr)

        return pr_generator

    yield create_review_list


@pytest.mark.parametrize(
    "review_list,config,expected",
    [
        (
            [
                {
                    "pr_id": "00001",
                    "pr_labels": [{"name": "bugs"}, {"name": "mergeable"}],
                    "reviews_info": [("NONE", "COMMENT"), ("OWNER", "REQUEST_CHANGES")],
                }
            ],
            {"merge_label": "mergeable"},
            [],
        ),
        (
            [
                {
                    "pr_id": "00002",
                    "pr_labels": [{"name": "mergeable"}],
                    "reviews_info": [("OWNER", "APPROVED")],
                }
            ],
            {"merge_label": "mergeable"},
            ["00002"],
        ),
        (
            [
                {
                    "pr_id": "00003",
                    "pr_labels": [{"name": "mergeable"}],
                    "reviews_info": [("OWNER", "APPROVED")],
                },
                {
                    "pr_id": "00004",
                    "pr_labels": [{"name": "mergeable"}],
                    "reviews_info": [
                        ("OWNER", "COMMENT"),
                        ("COLLABORATOR", "APPROVED"),
                    ],
                },
            ],
            {"merge_label": "mergeable"},
            ["00003", "00004"],
        ),
    ],
)
def test_get_mergeable_pr(review_list, config, expected, make_review_list):
    review_list = make_review_list(review_list)

    mergeable_id = []
    for pull_req in get_mergeable_pr(review_list, config):
        mergeable_id.append(pull_req.id)

    assert mergeable_id == expected
