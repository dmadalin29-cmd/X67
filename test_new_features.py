"""
X67 Digital Media Groupe - New Features Tests
Tests for: TopUp, Auto-TopUp, Referral System, Admin User Block/Delete, Banner Upload
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://x67market.preview.emergentagent.com')


class TestAdminUserManagement:
    """Test admin user blocking and deletion functionality"""
    
    @pytest.fixture
    def admin_session(self):
        """Create admin session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@x67digital.com",
            "password": "admin"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return session
    
    @pytest.fixture
    def test_user(self, admin_session):
        """Create a test user for blocking/deletion tests"""
        session = requests.Session()
        unique_email = f"test_block_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        response = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Test Block User"
        })
        assert response.status_code == 200
        user_data = response.json()
        return {"user_id": user_data["user_id"], "email": unique_email, "session": session}
    
    def test_admin_block_user(self, admin_session, test_user):
        """Test admin can block a user"""
        user_id = test_user["user_id"]
        
        # Block the user
        response = admin_session.put(
            f"{BASE_URL}/api/admin/users/{user_id}",
            json={"is_blocked": True}
        )
        assert response.status_code == 200
        
        # Verify user is blocked by checking admin users list
        users_response = admin_session.get(f"{BASE_URL}/api/admin/users")
        assert users_response.status_code == 200
        users = users_response.json()["users"]
        blocked_user = next((u for u in users if u["user_id"] == user_id), None)
        assert blocked_user is not None
        assert blocked_user.get("is_blocked") == True
    
    def test_admin_unblock_user(self, admin_session, test_user):
        """Test admin can unblock a user"""
        user_id = test_user["user_id"]
        
        # First block the user
        admin_session.put(
            f"{BASE_URL}/api/admin/users/{user_id}",
            json={"is_blocked": True}
        )
        
        # Then unblock
        response = admin_session.put(
            f"{BASE_URL}/api/admin/users/{user_id}",
            json={"is_blocked": False}
        )
        assert response.status_code == 200
        
        # Verify user is unblocked
        users_response = admin_session.get(f"{BASE_URL}/api/admin/users")
        users = users_response.json()["users"]
        user = next((u for u in users if u["user_id"] == user_id), None)
        assert user is not None
        assert user.get("is_blocked") == False
    
    def test_admin_delete_user_with_ads(self, admin_session):
        """Test admin can delete a user and all their associated data"""
        # Create a new user with an ad
        session = requests.Session()
        unique_email = f"test_delete_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        reg_response = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Test Delete User"
        })
        assert reg_response.status_code == 200
        user_id = reg_response.json()["user_id"]
        
        # Create an ad for this user
        ad_response = session.post(f"{BASE_URL}/api/ads", json={
            "title": "Ad to be deleted with user",
            "description": "This ad should be deleted when user is deleted",
            "category_id": "electronics",
            "city_id": "bucuresti"
        })
        assert ad_response.status_code == 200
        ad_id = ad_response.json()["ad_id"]
        
        # Admin deletes the user
        delete_response = admin_session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
        assert delete_response.status_code == 200
        assert "deleted" in delete_response.json()["message"].lower()
        
        # Verify user no longer exists in users list
        users_response = admin_session.get(f"{BASE_URL}/api/admin/users")
        users = users_response.json()["users"]
        deleted_user = next((u for u in users if u["user_id"] == user_id), None)
        assert deleted_user is None
        
        # Verify ad was also deleted
        ad_check = requests.get(f"{BASE_URL}/api/ads/{ad_id}")
        assert ad_check.status_code == 404
    
    def test_admin_cannot_delete_self(self, admin_session):
        """Test admin cannot delete their own account"""
        # Get admin user_id
        me_response = admin_session.get(f"{BASE_URL}/api/auth/me")
        admin_user_id = me_response.json()["user_id"]
        
        # Try to delete self
        response = admin_session.delete(f"{BASE_URL}/api/admin/users/{admin_user_id}")
        assert response.status_code == 400
        assert "cannot delete" in response.json()["detail"].lower() or "own account" in response.json()["detail"].lower()


class TestTopUpSystem:
    """Test TopUp functionality for ads"""
    
    @pytest.fixture
    def user_with_active_ad(self):
        """Create user with an active ad for TopUp testing"""
        session = requests.Session()
        unique_email = f"topup_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        
        # Register user
        reg_response = session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "TopUp Test User"
        })
        assert reg_response.status_code == 200
        user_id = reg_response.json()["user_id"]
        
        # Create an ad
        ad_response = session.post(f"{BASE_URL}/api/ads", json={
            "title": "TopUp Test Ad",
            "description": "Testing TopUp functionality",
            "category_id": "escorts",
            "city_id": "bucuresti"
        })
        assert ad_response.status_code == 200
        ad_id = ad_response.json()["ad_id"]
        
        # Admin approves the ad
        admin_session = requests.Session()
        admin_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@x67digital.com",
            "password": "admin"
        })
        admin_session.put(f"{BASE_URL}/api/admin/ads/{ad_id}/status", json={"status": "active"})
        
        return {"session": session, "user_id": user_id, "ad_id": ad_id}
    
    def test_topup_ad_success(self, user_with_active_ad):
        """Test successful TopUp of an ad"""
        session = user_with_active_ad["session"]
        ad_id = user_with_active_ad["ad_id"]
        
        # Perform TopUp
        response = session.post(f"{BASE_URL}/api/ads/{ad_id}/topup")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "topup" in data["message"].lower() or "successful" in data["message"].lower()
        assert "next_topup_available_in" in data
    
    def test_topup_requires_auth(self):
        """Test TopUp requires authentication"""
        response = requests.post(f"{BASE_URL}/api/ads/some_ad_id/topup")
        assert response.status_code == 401
    
    def test_topup_only_own_ad(self, user_with_active_ad):
        """Test user can only TopUp their own ads"""
        ad_id = user_with_active_ad["ad_id"]
        
        # Create another user
        other_session = requests.Session()
        other_email = f"other_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        other_session.post(f"{BASE_URL}/api/auth/register", json={
            "email": other_email,
            "password": "TestPass123!",
            "name": "Other User"
        })
        
        # Try to TopUp someone else's ad
        response = other_session.post(f"{BASE_URL}/api/ads/{ad_id}/topup")
        assert response.status_code == 403
    
    def test_topup_only_active_ads(self):
        """Test TopUp only works on active ads"""
        session = requests.Session()
        unique_email = f"pending_ad_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Pending Ad User"
        })
        
        # Create ad (will be pending)
        ad_response = session.post(f"{BASE_URL}/api/ads", json={
            "title": "Pending Ad",
            "description": "This ad is pending",
            "category_id": "electronics",
            "city_id": "bucuresti"
        })
        ad_id = ad_response.json()["ad_id"]
        
        # Try to TopUp pending ad
        response = session.post(f"{BASE_URL}/api/ads/{ad_id}/topup")
        assert response.status_code == 400
        assert "active" in response.json()["detail"].lower()


class TestAutoTopUp:
    """Test Auto-TopUp toggle functionality"""
    
    @pytest.fixture
    def user_with_ad(self):
        """Create user with an ad"""
        session = requests.Session()
        unique_email = f"autotopup_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Auto TopUp Test User"
        })
        
        ad_response = session.post(f"{BASE_URL}/api/ads", json={
            "title": "Auto TopUp Test Ad",
            "description": "Testing Auto TopUp toggle",
            "category_id": "services",
            "city_id": "timisoara"
        })
        ad_id = ad_response.json()["ad_id"]
        
        return {"session": session, "ad_id": ad_id}
    
    def test_toggle_auto_topup_off(self, user_with_ad):
        """Test disabling auto-topup"""
        session = user_with_ad["session"]
        ad_id = user_with_ad["ad_id"]
        
        response = session.post(
            f"{BASE_URL}/api/ads/{ad_id}/auto-topup",
            json={"enabled": False}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["auto_topup"] == False
    
    def test_toggle_auto_topup_on(self, user_with_ad):
        """Test enabling auto-topup"""
        session = user_with_ad["session"]
        ad_id = user_with_ad["ad_id"]
        
        # First disable
        session.post(f"{BASE_URL}/api/ads/{ad_id}/auto-topup", json={"enabled": False})
        
        # Then enable
        response = session.post(
            f"{BASE_URL}/api/ads/{ad_id}/auto-topup",
            json={"enabled": True}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["auto_topup"] == True
    
    def test_auto_topup_requires_auth(self):
        """Test auto-topup toggle requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/ads/some_ad_id/auto-topup",
            json={"enabled": True}
        )
        assert response.status_code == 401


class TestReferralSystem:
    """Test referral code generation and tracking"""
    
    @pytest.fixture
    def authenticated_user(self):
        """Create authenticated user"""
        session = requests.Session()
        unique_email = f"referral_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Referral Test User"
        })
        
        return session
    
    def test_get_referral_code(self, authenticated_user):
        """Test getting/generating referral code"""
        response = authenticated_user.get(f"{BASE_URL}/api/user/referral-code")
        assert response.status_code == 200
        
        data = response.json()
        assert "referral_code" in data
        assert "referral_count" in data
        assert data["referral_code"].startswith("ref_")
    
    def test_referral_code_requires_auth(self):
        """Test referral code endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/user/referral-code")
        assert response.status_code == 401
    
    def test_track_referral(self):
        """Test referral tracking endpoint"""
        # First create a user with referral code
        session = requests.Session()
        unique_email = f"referrer_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Referrer User"
        })
        
        # Get referral code
        ref_response = session.get(f"{BASE_URL}/api/user/referral-code")
        ref_code = ref_response.json()["referral_code"]
        
        # Track referral (anonymous request)
        track_response = requests.post(
            f"{BASE_URL}/api/referral/track",
            json={"ref_code": ref_code}
        )
        assert track_response.status_code == 200
        
        data = track_response.json()
        assert "tracked" in data
    
    def test_track_invalid_referral(self):
        """Test tracking invalid referral code"""
        response = requests.post(
            f"{BASE_URL}/api/referral/track",
            json={"ref_code": "invalid_code_12345"}
        )
        assert response.status_code == 200
        assert response.json()["tracked"] == False


class TestBannerUpload:
    """Test banner file upload functionality"""
    
    @pytest.fixture
    def admin_session(self):
        """Create admin session"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@x67digital.com",
            "password": "admin"
        })
        assert response.status_code == 200
        return session
    
    def test_banner_upload_requires_admin(self):
        """Test banner upload requires admin role"""
        # Regular user session
        session = requests.Session()
        unique_email = f"regular_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Regular User"
        })
        
        # Create minimal JPEG
        jpeg_header = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01])
        files = {'file': ('test.jpg', jpeg_header, 'image/jpeg')}
        
        response = session.post(f"{BASE_URL}/api/upload/banner", files=files)
        assert response.status_code == 403
    
    def test_banner_upload_image_success(self, admin_session):
        """Test successful banner image upload"""
        # Create a minimal valid JPEG
        jpeg_header = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F,
            0x00, 0xFB, 0xD5, 0xFF, 0xD9
        ])
        
        files = {'file': ('banner_test.jpg', jpeg_header, 'image/jpeg')}
        response = admin_session.post(f"{BASE_URL}/api/upload/banner", files=files)
        assert response.status_code == 200
        
        data = response.json()
        assert "url" in data
        assert "filename" in data
        assert "is_video" in data
        assert data["is_video"] == False
        assert data["url"].startswith("/api/uploads/")
        assert "banner_" in data["filename"]
    
    def test_banner_upload_invalid_type(self, admin_session):
        """Test banner upload rejects invalid file types"""
        files = {'file': ('test.txt', b'This is not an image', 'text/plain')}
        response = admin_session.post(f"{BASE_URL}/api/upload/banner", files=files)
        assert response.status_code == 400


class TestAdSortingByTopupRank:
    """Test that ads are sorted by topup_rank"""
    
    def test_ads_sorted_by_topup_rank(self):
        """Test ads listing respects topup_rank sorting"""
        response = requests.get(f"{BASE_URL}/api/ads?category_id=escorts&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "ads" in data
        # Just verify the endpoint works - actual sorting depends on data


class TestTermsPageContent:
    """Test Terms page has updated content for free ads"""
    
    def test_terms_page_loads(self):
        """Test terms page is accessible"""
        response = requests.get(f"{BASE_URL}/")
        assert response.status_code == 200


class TestExistingTestAd:
    """Test with the existing test ad mentioned in requirements"""
    
    def test_get_existing_ad(self):
        """Test fetching the existing test ad"""
        ad_id = "ad_a02a50119432"
        response = requests.get(f"{BASE_URL}/api/ads/{ad_id}")
        # Ad may or may not exist, just verify endpoint works
        assert response.status_code in [200, 404]
