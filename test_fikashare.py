import os
import sys
import json
import time
import shutil
import tempfile
import unittest

from profile_parser import parse_profile_file, scan_local_profiles, ProfileInfo
from sync_engine import SyncItem, SyncStatus, BackupManager
from upnp_tunnel import ConnectionCode
from server import FikaShareServer
from client import FikaClient

class TestFikaShareCore(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fikashare_test_")
        self.spt_dir = os.path.join(self.test_dir, "SPT")
        self.profiles_dir = os.path.join(self.spt_dir, "user", "profiles")
        os.makedirs(self.profiles_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_mock_profile(self, profile_id: str, nickname: str, level: int, side: str) -> str:
        filepath = os.path.join(self.profiles_dir, f"{profile_id}.json")
        data = {
            "characters": {
                "pmc": {
                    "Info": {
                        "Nickname": nickname,
                        "Level": level,
                        "Side": side
                    }
                }
            }
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return filepath

    def test_resolve_profiles_dir(self):
        from profile_parser import resolve_profiles_dir
        self.create_mock_profile("prof_path_test", "PathTester", 15, "Usec")

        # 1. Test when configured path is SPT Root
        res_root = resolve_profiles_dir(self.spt_dir)
        self.assertEqual(res_root, os.path.abspath(self.profiles_dir))

        # 2. Test when configured path is user/profiles directly
        res_direct = resolve_profiles_dir(self.profiles_dir)
        self.assertEqual(res_direct, os.path.abspath(self.profiles_dir))

        # 3. Test when configured path is user folder
        user_dir = os.path.join(self.spt_dir, "user")
        res_user = resolve_profiles_dir(user_dir)
        self.assertEqual(res_user, os.path.abspath(self.profiles_dir))

    def test_profile_parser(self):
        fp = self.create_mock_profile("profile_123", "KillaSlayer", 35, "Usec")
        pinfo = parse_profile_file(fp)

        self.assertIsNotNone(pinfo)
        self.assertEqual(pinfo.profile_id, "profile_123")
        self.assertEqual(pinfo.nickname, "KillaSlayer")
        self.assertEqual(pinfo.level, 35)
        self.assertEqual(pinfo.side, "USEC")

    def test_sync_item_logic(self):
        p1 = ProfileInfo("pid1", "Player1", 10, "USEC", mtime=1000.0, file_size=500, file_path="p1")
        p2_newer = ProfileInfo("pid1", "Player1", 10, "USEC", mtime=1050.0, file_size=500, file_path="p1")
        p2_older = ProfileInfo("pid1", "Player1", 10, "USEC", mtime=950.0, file_size=500, file_path="p1")

        # Local only
        item_local_only = SyncItem("pid1", p1, None)
        self.assertEqual(item_local_only.status, SyncStatus.LOCAL_ONLY)
        self.assertTrue(item_local_only.can_upload)
        self.assertFalse(item_local_only.can_download)

        # Server only
        item_remote_only = SyncItem("pid1", None, p1)
        self.assertEqual(item_remote_only.status, SyncStatus.REMOTE_ONLY)
        self.assertFalse(item_remote_only.can_upload)
        self.assertTrue(item_remote_only.can_download)

        # Local newer
        item_local_newer = SyncItem("pid1", p2_newer, p1)
        self.assertEqual(item_local_newer.status, SyncStatus.LOCAL_NEWER)
        self.assertTrue(item_local_newer.can_upload)
        self.assertTrue(item_local_newer.can_download)

        # Server newer
        item_remote_newer = SyncItem("pid1", p2_older, p1)
        self.assertEqual(item_remote_newer.status, SyncStatus.REMOTE_NEWER)
        self.assertTrue(item_remote_newer.can_upload)
        self.assertTrue(item_remote_newer.can_download)

    def test_backup_isolation(self):
        fp = self.create_mock_profile("profile_backuptest", "BackupPlayer", 5, "Bear")
        custom_backup_dir = os.path.join(self.test_dir, "MyBackups")
        bm = BackupManager(backup_dir=custom_backup_dir)

        backup_file = bm.create_backup(fp, "profile_backuptest", action_label="unittest")
        self.assertIsNotNone(backup_file)
        self.assertTrue(os.path.exists(backup_file))
        
        # Verify backup is in custom_backup_dir and NOT in profiles_dir
        self.assertTrue(backup_file.startswith(os.path.abspath(custom_backup_dir)))
        self.assertFalse("user/profiles" in backup_file)

    def test_connection_code(self):
        code = ConnectionCode.encode("192.168.1.100", 8585, "secret123")
        self.assertTrue(code.startswith("FIKA-"))

        decoded = ConnectionCode.decode(code)
        self.assertIsNotNone(decoded)
        host, port, passphrase = decoded
        self.assertEqual(host, "192.168.1.100")
        self.assertEqual(port, 8585)
        self.assertEqual(passphrase, "secret123")

    def test_server_client_integration(self):
        # Setup Server SPT directory
        server_spt = os.path.join(self.test_dir, "ServerSPT")
        server_profiles = os.path.join(server_spt, "user", "profiles")
        os.makedirs(server_profiles, exist_ok=True)
        
        # Create server profile
        srv_file = os.path.join(server_profiles, "srv_prof.json")
        with open(srv_file, 'w') as f:
            json.dump({"characters": {"pmc": {"Info": {"Nickname": "ServerHostPMC", "Level": 50, "Side": "Bear"}}}}, f)

        # Setup Client SPT directory
        client_spt = os.path.join(self.test_dir, "ClientSPT")
        client_profiles = os.path.join(client_spt, "user", "profiles")
        os.makedirs(client_profiles, exist_ok=True)
        
        # Create client profile
        cli_file = os.path.join(client_profiles, "cli_prof.json")
        with open(cli_file, 'w') as f:
            json.dump({"characters": {"pmc": {"Info": {"Nickname": "ClientPMC", "Level": 20, "Side": "Usec"}}}}, f)

        # Start Server on test port 9595
        server = FikaShareServer()
        start_ok = server.start(spt_dir=server_spt, port=9595, passphrase="testpassphrase", enable_upnp=False)
        self.assertTrue(start_ok)

        try:
            time.sleep(0.5)

            # Test Client connection
            client = FikaClient()
            client.set_connection("127.0.0.1:9595", passphrase="testpassphrase")
            conn_ok, conn_msg = client.test_connection()
            self.assertTrue(conn_ok, f"Connection failed: {conn_msg}")

            # Test profile fetching
            ok, remotes, err = client.fetch_remote_profiles()
            self.assertTrue(ok)
            self.assertIn("srv_prof", remotes)
            self.assertEqual(remotes["srv_prof"].nickname, "ServerHostPMC")

            # Test downloading srv_prof to client default path
            dl_ok, dl_msg = client.download_profile("srv_prof", client_spt)
            self.assertTrue(dl_ok, f"Download failed: {dl_msg}")
            self.assertTrue(os.path.exists(os.path.join(client_profiles, "srv_prof.json")))

            # Test downloading srv_prof to custom path
            custom_target = os.path.join(self.test_dir, "CustomDownloads", "my_custom_profile.json")
            dl_cust_ok, dl_cust_msg = client.download_profile_to_path("srv_prof", custom_target)
            self.assertTrue(dl_cust_ok, f"Custom download failed: {dl_cust_msg}")
            self.assertTrue(os.path.exists(custom_target))

            # Test uploading cli_prof to server
            ul_ok, ul_msg = client.upload_profile("cli_prof", client_spt)
            self.assertTrue(ul_ok, f"Upload failed: {ul_msg}")
            self.assertTrue(os.path.exists(os.path.join(server_profiles, "cli_prof.json")))

        finally:
            server.stop()

if __name__ == '__main__':
    unittest.main()
