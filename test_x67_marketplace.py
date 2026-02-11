"""
X67 Digital Media Groupe - Backend API Tests
Tests for: Categories, Cities, Auth, Ads, Admin, Image Upload
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://x67market.preview.emergentagent.com')

class TestPublicAPIs:
    """Test public API endpoints - Categories, Cities, Car Brands, Moto Brands"""
    
    def test_categories_returns_all_categories(self):
        """Test /api/categories returns all expected categories with subcategories"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200
        
        categories = response.json()
        assert isinstance(categories, list)
        assert len(categories) >= 8  # escorts, real_estate, cars, jobs, electronics, fashion, services, animals
        
        # Verify structure
        for cat in categories:
            assert "id" in cat
            assert "name" in cat
            assert "icon" in cat
            assert "color" in cat
            assert "subcategories" in cat
        
        # Verify expected categories exist
        category_ids = [cat['id'] for cat in categories]
        expected = ['escorts', 'real_estate', 'cars', 'jobs', 'electronics', 'fashion', 'services', 'animals']
        for expected_cat in expected:
            assert expected_cat in category_ids, f"Missing category: {expected_cat}"
    
    def test_real_estate_has_extensive_subcategories(self):
        """Test real estate category has all subcategories"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200
        
        categories = response.json()
        real_estate = next((c for c in categories if c['id'] == 'real_estate'), None)
        assert real_estate is not None
        
        subcategory_ids = [s['id'] for s in real_estate['subcategories']]
        expected_subs = ['apartments_sale', 'apartments_rent', 'houses_sale', 'houses_rent', 'land', 'commercial', 'offices', 'garages']
        for sub in expected_subs:
            assert sub in subcategory_ids, f"Missing real estate subcategory: {sub}"
    
    def test_jobs_has_extensive_subcategories(self):
        """Test jobs category has all subcategories"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200
        
        categories = response.json()
        jobs = next((c for c in categories if c['id'] == 'jobs'), None)
        assert jobs is not None
        
        # Jobs should have 20+ subcategories
        assert len(jobs['subcategories']) >= 15
        
        subcategory_ids = [s['id'] for s in jobs['subcategories']]
        expected_subs = ['jobs_driver', 'jobs_it', 'jobs_sales', 'jobs_horeca', 'jobs_remote', 'jobs_abroad']
        for sub in expected_subs:
            assert sub in subcategory_ids, f"Missing jobs subcategory: {sub}"
    
    def test_cities_returns_romanian_cities(self):
        """Test /api/cities returns Romanian cities"""
        response = requests.get(f"{BASE_URL}/api/cities")
        assert response.status_code == 200
        
        cities = response.json()
        assert isinstance(cities, list)
        assert len(cities) >= 30  # Should have 40+ Romanian cities
        
        # Verify structure
        for city in cities:
            assert "id" in city
            assert "name" in city
            assert "county" in city
        
        # Verify major cities
        city_names = [c['name'] for c in cities]
        major_cities = ['București', 'Cluj-Napoca', 'Timișoara', 'Iași', 'Constanța', 'Brașov']
        for city in major_cities:
            assert city in city_names, f"Missing major city: {city}"
    
    def test_car_brands_returns_brands_with_models(self):
        """Test /api/car-brands returns car brands with models"""
        response = requests.get(f"{BASE_URL}/api/car-brands")
        assert response.status_code == 200
        
        brands = response.json()
        assert isinstance(brands, dict)
        assert len(brands) >= 15
        
        # Verify structure
        for brand_key, brand_data in brands.items():
            assert "name" in brand_data
            assert "models" in brand_data
            assert isinstance(brand_data['models'], list)
            assert len(brand_data['models']) > 0
        
        # Verify popular brands
        expected_brands = ['bmw', 'mercedes', 'audi', 'volkswagen', 'toyota', 'dacia', 'tesla']
        for brand in expected_brands:
            assert brand in brands, f"Missing car brand: {brand}"
    
    def test_moto_brands_returns_brands_with_models(self):
        """Test /api/moto-brands returns motorcycle brands with models"""
        response = requests.get(f"{BASE_URL}/api/moto-brands")
        assert response.status_code == 200
        
        brands = response.json()
        assert isinstance(brands, dict)
        assert len(brands) >= 10
        
        # Verify structure
        for brand_key, brand_data in brands.items():
            assert "name" in brand_data
            assert "models" in brand_data
        
        # Verify popular moto brands
        expected_brands = ['honda_moto', 'yamaha', 'kawasaki', 'ducati', 'bmw_moto', 'harley']
        for brand in expected_brands:
            assert brand in brands, f"Missing moto brand: {brand}"


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    @pytest.fixture
    def unique_email(self):
        return f"test_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
    
    def test_user_registration_success(self, unique_email):
        """Test user registration with valid data"""
        user_data = {
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Test User",
            "phone": "+40123456789"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "user_id" in data
        assert data["email"] == unique_email
        assert data["name"] == "Test User"
        assert data["role"] == "user"
    
    def test_user_registration_duplicate_email_fails(self, unique_email):
        """Test registration fails with duplicate email"""
        user_data = {
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Test User"
        }
        
        # First registration
        response1 = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
        assert response1.status_code == 200
        
        # Second registration with same email should fail
        response2 = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
        assert response2.status_code == 400
    
    def test_user_login_success(self, unique_email):
        """Test user login with valid credentials"""
        # First register
        user_data = {
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Test User"
        }
        requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
        
        # Then login
        login_data = {
            "email": unique_email,
            "password": "TestPass123!"
        }
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "user_id" in data
        assert data["email"] == unique_email
    
    def test_user_login_invalid_credentials(self):
        """Test login fails with invalid credentials"""
        login_data = {
            "email": "nonexistent@test.com",
            "password": "wrongpassword"
        }
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        assert response.status_code == 401
    
    def test_admin_login_success(self):
        """Test admin login with correct credentials"""
        admin_data = {
            "email": "admin@x67digital.com",
            "password": "admin"
        }
        response = requests.post(f"{BASE_URL}/api/auth/login", json=admin_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["role"] == "admin"
        assert data["email"] == "admin@x67digital.com"
    
    def test_auth_me_requires_authentication(self):
        """Test /api/auth/me requires authentication"""
        # Create new session without cookies
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401


class TestAdsEndpoints:
    """Test ads-related endpoints"""
    
    @pytest.fixture
    def authenticated_session(self):
        """Create authenticated session"""
        session = requests.Session()
        unique_email = f"ads_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        
        # Register user
        user_data = {
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Ads Test User"
        }
        session.post(f"{BASE_URL}/api/auth/register", json=user_data)
        
        return session
    
    @pytest.fixture
    def admin_session(self):
        """Create admin authenticated session"""
        session = requests.Session()
        admin_data = {
            "email": "admin@x67digital.com",
            "password": "admin"
        }
        session.post(f"{BASE_URL}/api/auth/login", json=admin_data)
        return session
    
    def test_get_ads_public(self):
        """Test getting ads list (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/ads?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "ads" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data
        assert isinstance(data["ads"], list)
    
    def test_get_ads_with_category_filter(self):
        """Test getting ads filtered by category"""
        response = requests.get(f"{BASE_URL}/api/ads?category_id=cars&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "ads" in data
    
    def test_get_promoted_ads(self):
        """Test getting promoted ads"""
        response = requests.get(f"{BASE_URL}/api/ads/promoted?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_ad_requires_auth(self):
        """Test creating ad requires authentication"""
        session = requests.Session()  # New session without auth
        ad_data = {
            "title": "Test Ad",
            "description": "Test description",
            "category_id": "cars",
            "city_id": "bucuresti"
        }
        response = session.post(f"{BASE_URL}/api/ads", json=ad_data)
        assert response.status_code == 401
    
    def test_create_ad_success(self, authenticated_session):
        """Test creating ad with authenticated user (FREE - no payment required)"""
        ad_data = {
            "title": "Test Car for Sale",
            "description": "This is a test car listing for API testing",
            "category_id": "cars",
            "subcategory_id": "cars_sale",
            "city_id": "bucuresti",
            "price": 15000,
            "price_type": "negotiable",
            "contact_phone": "+40123456789"
        }
        
        response = authenticated_session.post(f"{BASE_URL}/api/ads", json=ad_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "ad_id" in data
        assert data["status"] == "pending"  # Ad is pending approval
        
        return data["ad_id"]
    
    def test_get_ad_by_id(self, authenticated_session):
        """Test getting ad by ID"""
        # First create an ad
        ad_data = {
            "title": "Test Ad for Retrieval",
            "description": "Test description",
            "category_id": "real_estate",
            "city_id": "cluj"
        }
        create_response = authenticated_session.post(f"{BASE_URL}/api/ads", json=ad_data)
        ad_id = create_response.json()["ad_id"]
        
        # Get the ad
        response = requests.get(f"{BASE_URL}/api/ads/{ad_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ad_id"] == ad_id
        assert data["title"] == "Test Ad for Retrieval"


class TestAdminEndpoints:
    """Test admin-specific endpoints"""
    
    @pytest.fixture
    def admin_session(self):
        """Create admin authenticated session"""
        session = requests.Session()
        admin_data = {
            "email": "admin@x67digital.com",
            "password": "admin"
        }
        response = session.post(f"{BASE_URL}/api/auth/login", json=admin_data)
        assert response.status_code == 200
        return session
    
    def test_admin_stats(self, admin_session):
        """Test admin stats endpoint"""
        response = admin_session.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_users" in data
        assert "total_ads" in data
        assert "pending_ads" in data
        assert "active_ads" in data
        assert "total_payments" in data
        assert "total_revenue" in data
    
    def test_admin_users_list(self, admin_session):
        """Test admin users list endpoint"""
        response = admin_session.get(f"{BASE_URL}/api/admin/users?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data
        assert isinstance(data["users"], list)
    
    def test_admin_ads_list(self, admin_session):
        """Test admin ads list endpoint"""
        response = admin_session.get(f"{BASE_URL}/api/admin/ads?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "ads" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data
    
    def test_admin_ads_filter_by_status(self, admin_session):
        """Test admin ads list filtered by status"""
        response = admin_session.get(f"{BASE_URL}/api/admin/ads?status=pending&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "ads" in data
    
    def test_admin_approve_ad(self, admin_session):
        """Test admin approving an ad"""
        # First create an ad as a regular user
        user_session = requests.Session()
        unique_email = f"approve_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        user_session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Approve Test User"
        })
        
        ad_response = user_session.post(f"{BASE_URL}/api/ads", json={
            "title": "Ad to Approve",
            "description": "Test ad for approval",
            "category_id": "electronics",
            "city_id": "timisoara"
        })
        ad_id = ad_response.json()["ad_id"]
        
        # Admin approves the ad
        response = admin_session.put(f"{BASE_URL}/api/admin/ads/{ad_id}/status", json={"status": "active"})
        assert response.status_code == 200
        
        # Verify ad is now active
        ad_check = requests.get(f"{BASE_URL}/api/ads/{ad_id}")
        assert ad_check.json()["status"] == "active"
    
    def test_admin_reject_ad(self, admin_session):
        """Test admin rejecting an ad"""
        # Create an ad
        user_session = requests.Session()
        unique_email = f"reject_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        user_session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Reject Test User"
        })
        
        ad_response = user_session.post(f"{BASE_URL}/api/ads", json={
            "title": "Ad to Reject",
            "description": "Test ad for rejection",
            "category_id": "fashion",
            "city_id": "iasi"
        })
        ad_id = ad_response.json()["ad_id"]
        
        # Admin rejects the ad
        response = admin_session.put(f"{BASE_URL}/api/admin/ads/{ad_id}/status", json={"status": "rejected"})
        assert response.status_code == 200
        
        # Verify ad is rejected
        ad_check = requests.get(f"{BASE_URL}/api/ads/{ad_id}")
        assert ad_check.json()["status"] == "rejected"
    
    def test_admin_endpoints_require_admin_role(self):
        """Test admin endpoints require admin role"""
        # Create regular user session
        session = requests.Session()
        unique_email = f"regular_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Regular User"
        })
        
        # Try to access admin endpoints
        response = session.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 403  # Forbidden


class TestBannersEndpoint:
    """Test banners endpoint"""
    
    def test_get_homepage_banners(self):
        """Test getting homepage banners"""
        response = requests.get(f"{BASE_URL}/api/banners?position=homepage")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)


class TestImageUpload:
    """Test image upload functionality"""
    
    @pytest.fixture
    def authenticated_session(self):
        """Create authenticated session"""
        session = requests.Session()
        unique_email = f"upload_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Upload Test User"
        })
        return session
    
    def test_upload_requires_auth(self):
        """Test image upload requires authentication"""
        session = requests.Session()
        # Create a simple test image
        files = {'file': ('test.jpg', b'\xff\xd8\xff\xe0\x00\x10JFIF', 'image/jpeg')}
        response = session.post(f"{BASE_URL}/api/upload", files=files)
        assert response.status_code == 401
    
    def test_upload_image_success(self, authenticated_session):
        """Test successful image upload"""
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
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
            0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
            0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
            0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
            0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
            0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
            0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
            0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xFF, 0xD9
        ])
        
        files = {'file': ('test.jpg', jpeg_header, 'image/jpeg')}
        response = authenticated_session.post(f"{BASE_URL}/api/upload", files=files)
        assert response.status_code == 200
        
        data = response.json()
        assert "url" in data
        assert "filename" in data
        assert data["url"].startswith("/api/uploads/")


class TestFreeAdCreation:
    """Test free ad creation flow (payment disabled)"""
    
    def test_ad_creation_is_free(self):
        """Test that ad creation works without payment"""
        session = requests.Session()
        unique_email = f"free_ad_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com"
        
        # Register user
        session.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Free Ad Test User"
        })
        
        # Create ad directly without payment
        ad_data = {
            "title": "Free Ad Test",
            "description": "Testing free ad creation without payment",
            "category_id": "services",
            "subcategory_id": "it_services",
            "city_id": "bucuresti",
            "price": 100,
            "price_type": "fixed"
        }
        
        response = session.post(f"{BASE_URL}/api/ads", json=ad_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "ad_id" in data
        assert data["status"] == "pending"  # Ad created, pending admin approval
