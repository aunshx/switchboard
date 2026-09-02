from __future__ import annotations

import unittest

from backend.googledrive_mock import (
    GoogleDriveMockError,
    get_tool_registry,
    googledrive_add_file_sharing_preference,
    googledrive_copy_file,
    googledrive_create_comment,
    googledrive_create_drive,
    googledrive_create_file,
    googledrive_create_file_from_text,
    googledrive_create_folder,
    googledrive_create_reply,
    googledrive_create_shortcut_to_file,
    googledrive_delete_comment,
    googledrive_delete_drive,
    googledrive_delete_permission,
    googledrive_delete_reply,
    googledrive_download_file,
    googledrive_edit_file,
    googledrive_empty_trash,
    googledrive_files_modify_labels,
    googledrive_find_file,
    googledrive_find_folder,
    googledrive_generate_ids,
    reset_googledrive_mock_state,
)
from backend.main import list_available_tools


class GoogleDriveMockTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_googledrive_mock_state()

    def test_registry_exposes_all_drive_tools(self) -> None:
        registry = get_tool_registry()
        self.assertEqual(20, len(registry))
        available_tools = set(list_available_tools())
        self.assertTrue(set(registry).issubset(available_tools))
        self.assertTrue(callable(registry["GOOGLEDRIVE_FIND_FILE"].callable))

    def test_find_download_edit_and_copy_are_stateful(self) -> None:
        search = googledrive_find_file(
            q="name contains 'Revenue' and trashed=false", pageSize=5
        )
        self.assertEqual(1, len(search.files))
        self.assertEqual("Revenue Model.csv", search.files[0].name)

        downloaded = googledrive_download_file(
            file_id="file_001", mime_type="application/pdf"
        )
        self.assertIn("Revenue finished 8 percent above plan", downloaded.content)
        self.assertEqual("application/pdf", downloaded.mimeType)

        edited = googledrive_edit_file(
            file_id="file_002",
            content="region,revenue\nwest,1400000\n",
            mime_type="text/csv",
        )
        self.assertIn("1400000", edited.content)

        copied = googledrive_copy_file(
            file_id="file_002", new_title="Revenue Model - Copy.csv"
        )
        self.assertEqual("Revenue Model - Copy.csv", copied.name)

    def test_create_file_folder_and_shortcut_mutate_search_results(self) -> None:
        folder = googledrive_create_folder(
            folder_name="Quarterly Drafts", parent_id="fld_001"
        )
        created = googledrive_create_file_from_text(
            file_name="Launch Risks.txt",
            text_content="Webinar QA remains the top launch risk.",
            parent_id=folder.id,
        )
        shortcut = googledrive_create_shortcut_to_file(
            name="Board Summary Shortcut",
            target_id="file_001",
        )

        self.assertEqual("Quarterly Drafts", folder.name)
        self.assertEqual("Launch Risks.txt", created.name)
        self.assertEqual("application/vnd.google-apps.shortcut", shortcut.mimeType)

        found = googledrive_find_file(q="launch risk", pageSize=10)
        names = {file.name for file in found.files}
        self.assertIn("Launch Risks.txt", names)

        metadata_file = googledrive_create_file(
            name="Blank Plan", mimeType="text/plain", parents=["root"]
        )
        self.assertEqual("Blank Plan", metadata_file.name)

    def test_comment_and_reply_lifecycle_is_stateful(self) -> None:
        comment = googledrive_create_comment(
            file_id="file_001", content="Need a stronger enterprise angle."
        )
        reply = googledrive_create_reply(
            file_id="file_001",
            comment_id=comment.id,
            content="Adding the enterprise detail now.",
            action="resolve",
        )
        self.assertEqual("resolve", reply.action)

        deleted_reply = googledrive_delete_reply(
            file_id="file_001", comment_id=comment.id, reply_id=reply.id
        )
        self.assertTrue(deleted_reply.deleted)

        deleted_comment = googledrive_delete_comment(
            file_id="file_001", comment_id=comment.id
        )
        self.assertTrue(deleted_comment.deleted)

    def test_permissions_labels_and_drive_lifecycle_are_stateful(self) -> None:
        sharing = googledrive_add_file_sharing_preference(
            file_id="file_002",
            role="commenter",
            type="user",
            email_address="legal@corp.com",
        )
        permission_id = sharing.permission.id
        self.assertEqual("commenter", sharing.permission.role)

        deleted_permission = googledrive_delete_permission(
            file_id="file_002", permission_id=permission_id
        )
        self.assertTrue(deleted_permission.deleted)

        labels = googledrive_files_modify_labels(
            file_id="file_002",
            label_modifications=[
                {
                    "label_id": "LBL_REVIEW",
                    "remove_label": False,
                    "field_modifications": [
                        {
                            "field_id": "status",
                            "kind": "drive#fieldModification",
                            "set_text_values": ["needs-review"],
                        }
                    ],
                }
            ],
        )
        self.assertTrue(
            any(label.id == "LBL_REVIEW" for label in labels.modifiedLabels)
        )

        drive = googledrive_create_drive(
            name="Deal Desk", requestId="drive-create-deal-desk"
        )
        self.assertEqual("Deal Desk", drive.name)
        deleted_drive = googledrive_delete_drive(
            driveId=drive.id, allowItemDeletion=True
        )
        self.assertTrue(deleted_drive.deleted)

    def test_find_folder_generate_ids_empty_trash_and_errors_are_deterministic(
        self,
    ) -> None:
        folders = googledrive_find_folder(name_contains="Board", starred=True)
        self.assertEqual(1, folders.resultCount)
        self.assertEqual("Board Docs", folders.folders[0].name)

        generated = googledrive_generate_ids(count=3)
        self.assertEqual(3, len(generated.ids))

        deleted = googledrive_empty_trash()
        self.assertEqual(1, deleted.deletedCount)

        reset_googledrive_mock_state()
        after_reset = googledrive_find_file(q="trashed=true", pageSize=10)
        self.assertEqual(1, len(after_reset.files))

        with self.assertRaises(GoogleDriveMockError):
            googledrive_download_file(file_id="missing")

        with self.assertRaises(GoogleDriveMockError):
            googledrive_delete_permission(file_id="file_001", permission_id="missing")

        with self.assertRaises(GoogleDriveMockError):
            googledrive_delete_drive(driveId="drive_001", allowItemDeletion=False)


if __name__ == "__main__":
    unittest.main()
