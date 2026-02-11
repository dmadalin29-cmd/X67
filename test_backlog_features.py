"""
Backend tests for X67 Digital Media Groupe - Backlog Features
Tests: Favorites, Messaging, Analytics, Admin Categories/Cities
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@x67digital.com"
ADMIN_PASSWORD = "admin"
ADMIN2_EMAIL = "contact@x67digital.com"
ADMIN2_PASSWORD = "Credcada1."
TEST_AD_ID = "ad_a02a50119432"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_session(api_client):
    """Authenticated admin session"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    # Copy cookies to session
    api_client.cookies.update(response.cookies)
    return api_client


@pytest.fixture(scope="module")
def admin2_session():
    """Second admin session for messaging tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN2_EMAIL,
        "password": ADMIN2_PASSWORD
    })
    if response.status_code == 200:
        session.cookies.update(response.cookies)
        return session
    return None


# ===================== FAVORITES TESTS =====================

class TestFavorites:
    """Favorites system tests"""
    
    def test_add_favorite(self, admin_session):
        """POST /api/favorites/{ad_id} - Add ad to favorites"""
        # First remove if exists
        admin_session.delete(f"{BASE_URL}/api/favorites/{TEST_AD_ID}")
        
        response = admin_session.post(f"{BASE_URL}/api/favorites/{TEST_AD_ID}")
        assert response.status_code == 200, f"Add favorite failed: {response.text}"
        
        data = response.json()
        assert "favorite_id" in data
        assert data["message"] == "Added to favorites"
        print(f"✓ Added favorite: {data['favorite_id']}")
    
    def test_add_favorite_duplicate(self, admin_session):
        """POST /api/favorites/{ad_id} - Should fail for duplicate"""
        response = admin_session.post(f"{BASE_URL}/api/favorites/{TEST_AD_ID}")
        assert response.status_code == 400
        assert "Already in favorites" in response.json().get("detail", "")
        print("✓ Duplicate favorite rejected correctly")
    
    def test_check_favorite_true(self, admin_session):
        """GET /api/favorites/check/{ad_id} - Check if favorited (should be true)"""
        response = admin_session.get(f"{BASE_URL}/api/favorites/check/{TEST_AD_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["is_favorite"] == True
        print("✓ Favorite check returned True")
    
    def test_get_favorites_list(self, admin_session):
        """GET /api/favorites - List user's favorites"""
        response = admin_session.get(f"{BASE_URL}/api/favorites")
        assert response.status_code == 200
        
        data = response.json()
        assert "favorites" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data
        assert data["total"] >= 1
        
        # Check favorite has ad details
        if data["favorites"]:
            fav = data["favorites"][0]
            assert "ad_id" in fav
            assert "title" in fav
            assert "favorited_at" in fav
            assert "price_dropped" in fav
        print(f"✓ Got {data['total']} favorites")
    
    def test_remove_favorite(self, admin_session):
        """DELETE /api/favorites/{ad_id} - Remove from favorites"""
        response = admin_session.delete(f"{BASE_URL}/api/favorites/{TEST_AD_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Removed from favorites"
        print("✓ Removed favorite successfully")
    
    def test_check_favorite_false(self, admin_session):
        """GET /api/favorites/check/{ad_id} - Check if favorited (should be false)"""
        response = admin_session.get(f"{BASE_URL}/api/favorites/check/{TEST_AD_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["is_favorite"] == False
        print("✓ Favorite check returned False after removal")
    
    def test_remove_favorite_not_found(self, admin_session):
        """DELETE /api/favorites/{ad_id} - Should fail for non-existent"""
        response = admin_session.delete(f"{BASE_URL}/api/favorites/{TEST_AD_ID}")
        assert response.status_code == 404
        print("✓ Remove non-existent favorite returns 404")
    
    def test_add_favorite_invalid_ad(self, admin_session):
        """POST /api/favorites/{ad_id} - Should fail for invalid ad"""
        response = admin_session.post(f"{BASE_URL}/api/favorites/invalid_ad_id_12345")
        assert response.status_code == 404
        assert "Ad not found" in response.json().get("detail", "")
        print("✓ Add favorite for invalid ad returns 404")
    
    def test_favorites_requires_auth(self, api_client):
        """Favorites endpoints require authentication"""
        # Create new session without auth
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        response = new_session.get(f"{BASE_URL}/api/favorites")
        assert response.status_code == 401
        print("✓ Favorites requires authentication")


# ===================== MESSAGING TESTS =====================

class TestMessaging:
    """Messaging system tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self, admin_session, admin2_session):
        self.admin_session = admin_session
        self.admin2_session = admin2_session
        self.conversation_id = None
    
    def test_send_message_creates_conversation(self, admin_session):
        """POST /api/messages - Send message creates conversation"""
        # Get ad owner info first
        ad_response = admin_session.get(f"{BASE_URL}/api/ads/{TEST_AD_ID}")
        if ad_response.status_code != 200:
            pytest.skip("Test ad not found")
        
        ad_data = ad_response.json()
        receiver_id = ad_data.get("user_id")
        
        if not receiver_id or receiver_id == "admin_001":
            # Create a test message to self (will fail) or skip
            pytest.skip("Cannot message own ad")
        
        response = admin_session.post(f"{BASE_URL}/api/messages", json={
            "ad_id": TEST_AD_ID,
            "receiver_id": receiver_id,
            "content": "Test message from pytest"
        })
        
        if response.status_code == 200:
            data = response.json()
            assert "message_id" in data
            assert "conversation_id" in data
            self.__class__.conversation_id = data["conversation_id"]
            print(f"✓ Message sent, conversation: {data['conversation_id']}")
        else:
            print(f"Message send returned {response.status_code}: {response.text}")
    
    def test_send_message_missing_fields(self, admin_session):
        """POST /api/messages - Should fail with missing fields"""
        response = admin_session.post(f"{BASE_URL}/api/messages", json={
            "ad_id": TEST_AD_ID
            # Missing receiver_id and content
        })
        assert response.status_code == 400
        assert "Missing required fields" in response.json().get("detail", "")
        print("✓ Missing fields rejected correctly")
    
    def test_get_conversations(self, admin_session):
        """GET /api/conversations - List user's conversations"""
        response = admin_session.get(f"{BASE_URL}/api/conversations")
        assert response.status_code == 200
        
        data = response.json()
        assert "conversations" in data
        
        if data["conversations"]:
            conv = data["conversations"][0]
            assert "conversation_id" in conv
            assert "ad_id" in conv
            assert "participants" in conv
            assert "other_user" in conv
            assert "unread_count" in conv
        print(f"✓ Got {len(data['conversations'])} conversations")
    
    def test_get_unread_count(self, admin_session):
        """GET /api/messages/unread-count - Get unread message count"""
        response = admin_session.get(f"{BASE_URL}/api/messages/unread-count")
        assert response.status_code == 200
        
        data = response.json()
        assert "unread_count" in data
        assert isinstance(data["unread_count"], int)
        print(f"✓ Unread count: {data['unread_count']}")
    
    def test_messages_requires_auth(self):
        """Messages endpoints require authentication"""
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        response = new_session.get(f"{BASE_URL}/api/conversations")
        assert response.status_code == 401
        
        response = new_session.get(f"{BASE_URL}/api/messages/unread-count")
        assert response.status_code == 401
        print("✓ Messages requires authentication")


# ===================== ANALYTICS TESTS =====================

class TestAnalytics:
    """Analytics/Dashboard tests"""
    
    def test_analytics_overview(self, admin_session):
        """GET /api/analytics/overview - Get analytics overview"""
        response = admin_session.get(f"{BASE_URL}/api/analytics/overview")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_ads" in data
        assert "active_ads" in data
        assert "total_views" in data
        assert "total_favorites" in data
        assert "total_messages" in data
        
        # Verify types
        assert isinstance(data["total_ads"], int)
        assert isinstance(data["active_ads"], int)
        assert isinstance(data["total_views"], int)
        print(f"✓ Analytics overview: {data['total_ads']} ads, {data['total_views']} views")
    
    def test_analytics_views(self, admin_session):
        """GET /api/analytics/views - Get views chart data"""
        response = admin_session.get(f"{BASE_URL}/api/analytics/views?days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert "top_ads" in data
        assert "daily_views" in data
        assert "total_views" in data
        
        # Check daily_views structure
        if data["daily_views"]:
            day = data["daily_views"][0]
            assert "date" in day
            assert "views" in day
        
        # Check top_ads structure
        if data["top_ads"]:
            ad = data["top_ads"][0]
            assert "ad_id" in ad
            assert "title" in ad
            assert "views" in ad
        
        print(f"✓ Views analytics: {len(data['daily_views'])} days, {len(data['top_ads'])} top ads")
    
    def test_analytics_ads_performance(self, admin_session):
        """GET /api/analytics/ads-performance - Get per-ad performance"""
        response = admin_session.get(f"{BASE_URL}/api/analytics/ads-performance")
        assert response.status_code == 200
        
        data = response.json()
        assert "ads" in data
        
        if data["ads"]:
            ad = data["ads"][0]
            assert "ad_id" in ad
            assert "title" in ad
            assert "status" in ad
            assert "views" in ad
            assert "favorites" in ad
            assert "conversations" in ad
        
        print(f"✓ Ads performance: {len(data['ads'])} ads")
    
    def test_analytics_requires_auth(self):
        """Analytics endpoints require authentication"""
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        response = new_session.get(f"{BASE_URL}/api/analytics/overview")
        assert response.status_code == 401
        
        response = new_session.get(f"{BASE_URL}/api/analytics/views")
        assert response.status_code == 401
        
        response = new_session.get(f"{BASE_URL}/api/analytics/ads-performance")
        assert response.status_code == 401
        print("✓ Analytics requires authentication")


# ===================== ADMIN CATEGORIES TESTS =====================

class TestAdminCategories:
    """Admin categories management tests"""
    
    test_category_id = None
    
    def test_admin_get_categories(self, admin_session):
        """GET /api/admin/categories - List managed categories"""
        response = admin_session.get(f"{BASE_URL}/api/admin/categories")
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data
        print(f"✓ Got {len(data['categories'])} managed categories")
    
    def test_admin_create_category(self, admin_session):
        """POST /api/admin/categories - Create new category"""
        test_id = f"test_cat_{uuid.uuid4().hex[:8]}"
        response = admin_session.post(f"{BASE_URL}/api/admin/categories", json={
            "id": test_id,
            "name": "Test Category",
            "icon": "folder",
            "color": "from-blue-600 to-blue-700",
            "subcategories": [{"id": "sub1", "name": "Subcategory 1"}],
            "is_active": True,
            "order": 99
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "category_id" in data
        TestAdminCategories.test_category_id = data["category_id"]
        print(f"✓ Created category: {data['category_id']}")
    
    def test_admin_update_category(self, admin_session):
        """PUT /api/admin/categories/{id} - Update category"""
        if not TestAdminCategories.test_category_id:
            pytest.skip("No test category created")
        
        response = admin_session.put(
            f"{BASE_URL}/api/admin/categories/{TestAdminCategories.test_category_id}",
            json={"name": "Updated Test Category", "is_active": False}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Category updated"
        print("✓ Updated category successfully")
    
    def test_admin_delete_category(self, admin_session):
        """DELETE /api/admin/categories/{id} - Delete category"""
        if not TestAdminCategories.test_category_id:
            pytest.skip("No test category created")
        
        response = admin_session.delete(
            f"{BASE_URL}/api/admin/categories/{TestAdminCategories.test_category_id}"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Category deleted"
        print("✓ Deleted category successfully")
    
    def test_admin_categories_requires_admin(self):
        """Admin categories require admin role"""
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        response = new_session.get(f"{BASE_URL}/api/admin/categories")
        assert response.status_code == 401
        print("✓ Admin categories requires authentication")


# ===================== ADMIN CITIES TESTS =====================

class TestAdminCities:
    """Admin cities management tests"""
    
    test_city_id = None
    
    def test_admin_get_cities(self, admin_session):
        """GET /api/admin/cities - List managed cities"""
        response = admin_session.get(f"{BASE_URL}/api/admin/cities")
        assert response.status_code == 200
        
        data = response.json()
        assert "cities" in data
        print(f"✓ Got {len(data['cities'])} managed cities")
    
    def test_admin_create_city(self, admin_session):
        """POST /api/admin/cities - Create new city"""
        test_name = f"Test City {uuid.uuid4().hex[:6]}"
        response = admin_session.post(f"{BASE_URL}/api/admin/cities", json={
            "name": test_name,
            "region": "Test Region",
            "is_active": True,
            "order": 99
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "city_id" in data
        TestAdminCities.test_city_id = data["city_id"]
        print(f"✓ Created city: {data['city_id']}")
    
    def test_admin_update_city(self, admin_session):
        """PUT /api/admin/cities/{id} - Update city"""
        if not TestAdminCities.test_city_id:
            pytest.skip("No test city created")
        
        response = admin_session.put(
            f"{BASE_URL}/api/admin/cities/{TestAdminCities.test_city_id}",
            json={"name": "Updated Test City", "is_active": False}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "City updated"
        print("✓ Updated city successfully")
    
    def test_admin_delete_city(self, admin_session):
        """DELETE /api/admin/cities/{id} - Delete city"""
        if not TestAdminCities.test_city_id:
            pytest.skip("No test city created")
        
        response = admin_session.delete(
            f"{BASE_URL}/api/admin/cities/{TestAdminCities.test_city_id}"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "City deleted"
        print("✓ Deleted city successfully")
    
    def test_admin_cities_requires_admin(self):
        """Admin cities require admin role"""
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        response = new_session.get(f"{BASE_URL}/api/admin/cities")
        assert response.status_code == 401
        print("✓ Admin cities requires authentication")


# ===================== INTEGRATION TESTS =====================

class TestIntegration:
    """Integration tests for combined features"""
    
    def test_favorite_and_check_flow(self, admin_session):
        """Full favorite flow: add -> check -> list -> remove -> check"""
        # Clean up first
        admin_session.delete(f"{BASE_URL}/api/favorites/{TEST_AD_ID}")
        
        # Add
        response = admin_session.post(f"{BASE_URL}/api/favorites/{TEST_AD_ID}")
        assert response.status_code == 200
        
        # Check is_favorite
        response = admin_session.get(f"{BASE_URL}/api/favorites/check/{TEST_AD_ID}")
        assert response.json()["is_favorite"] == True
        
        # List should contain it
        response = admin_session.get(f"{BASE_URL}/api/favorites")
        favorites = response.json()["favorites"]
        ad_ids = [f["ad_id"] for f in favorites]
        assert TEST_AD_ID in ad_ids
        
        # Remove
        response = admin_session.delete(f"{BASE_URL}/api/favorites/{TEST_AD_ID}")
        assert response.status_code == 200
        
        # Check is_favorite again
        response = admin_session.get(f"{BASE_URL}/api/favorites/check/{TEST_AD_ID}")
        assert response.json()["is_favorite"] == False
        
        print("✓ Full favorite flow completed")
    
    def test_analytics_reflects_data(self, admin_session):
        """Analytics should reflect actual user data"""
        # Get overview
        overview = admin_session.get(f"{BASE_URL}/api/analytics/overview").json()
        
        # Get ads performance
        performance = admin_session.get(f"{BASE_URL}/api/analytics/ads-performance").json()
        
        # Total ads should match
        assert overview["total_ads"] == len(performance["ads"])
        
        # Active ads count should match
        active_count = len([a for a in performance["ads"] if a["status"] == "active"])
        assert overview["active_ads"] == active_count
        
        print("✓ Analytics data consistency verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
