
import traceback
import os
from dotenv import load_dotenv
import PyPDF2
import time
from io import BytesIO
import boto3
from botocore.client import Config
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

load_dotenv()


# AWS Textract Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def extract_text_with_ocr_from_pdf(file_obj, page_num):
    """Extract text from a specific PDF page using Amazon Textract"""
    try:
        # Create a new PDF with just the target page
        file_obj.seek(0)
        pdf_reader = PyPDF2.PdfReader(file_obj)
        
        # Create a new PDF writer with just the target page
        pdf_writer = PyPDF2.PdfWriter()
        pdf_writer.add_page(pdf_reader.pages[page_num])
        
        # Write the single page to a BytesIO buffer
        page_buffer = BytesIO()
        pdf_writer.write(page_buffer)
        page_buffer.seek(0)
        
        # Get the PDF bytes for Textract
        pdf_bytes = page_buffer.getvalue()
        
        print(f"Sending page {page_num + 1} to Amazon Textract...")
        ocr_time_start = time.time()
        
        try:
            # Create Textract client
            textract_client = boto3.client(
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
            
            # Call Textract detect_document_text
            response = textract_client.detect_document_text(
                Document={
                    'Bytes': pdf_bytes
                }
            )
            
            ocr_time_end = time.time()
            print(f"Amazon Textract completed in {ocr_time_end - ocr_time_start:.2f} seconds")
            
            # Extract text from Textract response
            extracted_text = ""
            line_text = ""
            
            # Process blocks to extract text
            for block in response['Blocks']:
                if block['BlockType'] == 'LINE':
                    line_text += block['Text'] + '\n'
                elif block['BlockType'] == 'WORD':
                    pass  # Individual words, we'll use LINE level for cleaner output
            
            # Calculate confidence statistics
            confidences = []
            for block in response['Blocks']:
                if 'Confidence' in block:
                    confidences.append(block['Confidence'])
            
            if confidences:
                avg_confidence = sum(confidences) / len(confidences)
                print(f"Page {page_num + 1}: Textract extracted {len(line_text)} characters with {avg_confidence:.1f}% avg confidence")
            else:
                print(f"Page {page_num + 1}: Textract extracted {len(line_text)} characters")
            
            return line_text.strip()
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"Textract API error for page {page_num + 1}: {error_code} - {error_message}")
            
            if error_code == 'InvalidParameterException':
                print("   Hint: Check PDF format and size")
            elif error_code == 'AccessDeniedException':
                print("   Hint: Check AWS permissions for Textract")
            elif error_code == 'ThrottlingException':
                print("   Hint: API rate limit exceeded, try again later")
            elif error_code == 'ProvisionedThroughputExceededException':
                print("   Hint: Textract capacity exceeded, try again later")
            
            return ""
            
        except (NoCredentialsError, PartialCredentialsError) as e:
            print(f"AWS credentials error for page {page_num + 1}: {e}")
            return ""
            
        except Exception as e:
            print(f"Unexpected Textract error for page {page_num + 1}: {str(e)}")
            return ""
                
    except Exception as e:
        print(f"Error in Textract processing for page {page_num + 1}: {str(e)}")
        traceback.print_exc()
        return ""