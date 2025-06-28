import os
import boto3
import ssl
import socket
import requests
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from botocore.config import Config
from dotenv import load_dotenv
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import json

# Load environment variables
load_dotenv()

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def test_ssl_handshake():
    """Test SSL handshake with AWS Textract endpoints."""
    print("=== Testing SSL Handshake ===")
    
    # AWS Textract endpoints to test
    endpoints = [
        f"textract.{AWS_REGION}.amazonaws.com",
        "textract.us-east-1.amazonaws.com",
        "textract.us-west-2.amazonaws.com"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"Testing SSL handshake with {endpoint}...")
            
            # Create SSL context
            context = ssl.create_default_context()
            
            # Test socket connection
            with socket.create_connection((endpoint, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=endpoint) as ssock:
                    print(f"✅ SSL handshake successful with {endpoint}")
                    print(f"   Protocol: {ssock.version()}")
                    print(f"   Cipher: {ssock.cipher()}")
                    
                    # Get certificate info
                    cert = ssock.getpeercert()
                    print(f"   Certificate Subject: {cert.get('subject', 'N/A')}")
                    print(f"   Certificate Issuer: {cert.get('issuer', 'N/A')}")
                    
        except Exception as e:
            print(f"❌ SSL handshake failed with {endpoint}: {e}")
        
        print()

def test_aws_credentials():
    """Test AWS credentials and connection."""
    print("=== Testing AWS Credentials ===")
    
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        print("❌ AWS credentials not found in environment variables")
        print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file")
        return False
    
    try:
        # Create boto3 client with explicit credentials
        client = boto3.client(
            'textract',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
            config=Config(
                connect_timeout=30,
                read_timeout=30,
                retries={'max_attempts': 3}
            )
        )
        
        # Test connection by calling list_adapters (lightweight operation)
        response = client.list_adapters()
        print(f"✅ AWS credentials valid")
        print(f"   Region: {AWS_REGION}")
        print(f"   Service: Amazon Textract")
        return True
        
    except NoCredentialsError:
        print("❌ AWS credentials not found")
        return False
    except PartialCredentialsError:
        print("❌ Incomplete AWS credentials")
        return False
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'UnauthorizedOperation':
            print("❌ AWS credentials valid but insufficient permissions for Textract")
        else:
            print(f"❌ AWS client error: {error_code} - {e.response['Error']['Message']}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def create_test_image():
    """Create a simple test image with text for OCR testing."""
    print("=== Creating Test Image ===")
    
    try:
        # Create a simple image with text
        width, height = 800, 600
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)
        
        # Try to use a default font, fallback to basic if not available
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            try:
                font = ImageFont.load_default()
                font = font.font_variant(size=40)
            except:
                font = ImageFont.load_default()
        
        # Add test text
        test_text = [
            "Amazon Textract OCR Test",
            "",
            "This is a test document for",
            "Amazon Textract text extraction.",
            "",
            "Test Date: 2024-01-01",
            "Test ID: ABC123XYZ",
            "",
            "Sample medical text:",
            "Patient: John Doe",
            "Diagnosis: Hypertension",
            "Medication: Lisinopril 10mg"
        ]
        
        y_position = 50
        line_height = 40
        
        for line in test_text:
            if line:  # Skip empty lines for positioning
                draw.text((50, y_position), line, fill='black', font=font)
            y_position += line_height
        
        # Save to BytesIO buffer
        img_buffer = BytesIO()
        image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        print("✅ Test image created successfully")
        return img_buffer.getvalue()
        
    except Exception as e:
        print(f"❌ Failed to create test image: {e}")
        return None

def test_textract_detect_text(image_bytes):
    """Test Amazon Textract detect_document_text function."""
    print("=== Testing Amazon Textract OCR ===")
    
    if not image_bytes:
        print("❌ No test image available")
        return False
    
    try:
        # Create Textract client
        client = boto3.client(
            'textract',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
            config=Config(
                connect_timeout=30,
                read_timeout=30,
                retries={'max_attempts': 3}
            )
        )
        
        print("Sending image to Amazon Textract...")
        
        # Call Textract
        response = client.detect_document_text(
            Document={
                'Bytes': image_bytes
            }
        )
        
        # Extract text from response
        extracted_text = ""
        line_text = ""
        
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE':
                line_text += block['Text'] + '\n'
            elif block['BlockType'] == 'WORD':
                pass  # Individual words, we'll use LINE level for cleaner output
        
        print("✅ Amazon Textract OCR successful!")
        print(f"   Blocks found: {len(response['Blocks'])}")
        print(f"   Text length: {len(line_text)} characters")
        print("\n--- Extracted Text ---")
        print(line_text)
        print("--- End Extracted Text ---\n")
        
        # Show confidence scores
        print("Confidence Analysis:")
        confidences = []
        for block in response['Blocks']:
            if 'Confidence' in block:
                confidences.append(block['Confidence'])
        
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            min_confidence = min(confidences)
            max_confidence = max(confidences)
            print(f"   Average confidence: {avg_confidence:.2f}%")
            print(f"   Min confidence: {min_confidence:.2f}%")
            print(f"   Max confidence: {max_confidence:.2f}%")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"❌ Textract API error: {error_code} - {error_message}")
        
        if error_code == 'InvalidParameterException':
            print("   Hint: Check image format and size")
        elif error_code == 'AccessDeniedException':
            print("   Hint: Check AWS permissions for Textract")
        elif error_code == 'ThrottlingException':
            print("   Hint: API rate limit exceeded, try again later")
        
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_https_requests():
    """Test HTTPS requests to AWS endpoints."""
    print("=== Testing HTTPS Requests ===")
    
    test_urls = [
        f"https://textract.{AWS_REGION}.amazonaws.com",
        "https://aws.amazon.com",
        "https://console.aws.amazon.com"
    ]
    
    for url in test_urls:
        try:
            print(f"Testing HTTPS request to {url}...")
            response = requests.get(url, timeout=10, verify=True)
            print(f"✅ HTTPS request successful (Status: {response.status_code})")
            
        except requests.exceptions.SSLError as e:
            print(f"❌ SSL Error with {url}: {e}")
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Connection Error with {url}: {e}")
        except requests.exceptions.Timeout as e:
            print(f"❌ Timeout Error with {url}: {e}")
        except Exception as e:
            print(f"❌ Unexpected error with {url}: {e}")

def main():
    """Run all tests."""
    print("Amazon Textract OCR Test Suite")
    print("=" * 50)
    print(f"AWS Region: {AWS_REGION}")
    print(f"AWS Access Key: {'✓' if AWS_ACCESS_KEY_ID else '✗'}")
    print(f"AWS Secret Key: {'✓' if AWS_SECRET_ACCESS_KEY else '✗'}")
    print()
    
    # Test 1: SSL Handshake
    test_ssl_handshake()
    
    # Test 2: HTTPS Requests
    test_https_requests()
    
    # Test 3: AWS Credentials
    credentials_valid = test_aws_credentials()
    
    if credentials_valid:
        # Test 4: Create test image
        test_image = create_test_image()
        
        # Test 5: Textract OCR
        if test_image:
            test_textract_detect_text(test_image)
    else:
        print("⚠️  Skipping Textract tests due to invalid credentials")
    
    print("\n" + "=" * 50)
    print("Test suite completed!")
    print("\nTo set up AWS credentials:")
    print("1. Create AWS account and get access keys")
    print("2. Add to .env file:")
    print("   AWS_ACCESS_KEY_ID=your_access_key")
    print("   AWS_SECRET_ACCESS_KEY=your_secret_key")
    print("   AWS_REGION=us-east-1")
    print("3. Ensure IAM user has Textract permissions")

if __name__ == "__main__":
    main() 