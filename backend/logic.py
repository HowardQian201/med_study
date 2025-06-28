from dotenv import load_dotenv
import psutil
import platform
import os
import PyPDF2
import requests
import json
import time
import uuid
import gc
from io import BytesIO
from .aws_ocr import extract_text_with_ocr_from_pdf

load_dotenv()


# Configuration constants
OCR_AVAILABLE = True
OCR_TEXT_THRESHOLD = 50  # Minimum characters to trigger OCR fallback
OCR_DPI = 300  # DPI for OCR image conversion (balance between quality and memory)

# Global variable to track peak memory usage
_peak_memory_usage = 0

def get_container_memory_limit():
    """Get the actual memory limit for the container"""
    try:
        
        # Try to read from cgroups v2
        try:
            with open('/sys/fs/cgroup/memory.max', 'r') as f:
                limit_str = f.read().strip()
                if limit_str == 'max':
                    raise Exception("No cgroup limit set")
                return int(limit_str)
        except:
            print("Error reading memory limit from cgroups v2")
            pass

        # Try to read from cgroups v1
        try:
            with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f:
                limit = int(f.read().strip())
                # If limit is very large, it's probably not set (default is 9223372036854775807)
                if limit > 1024 * 1024 * 1024 * 1024:  # 1TB
                    raise Exception("No cgroup limit set")
                return limit
        except:
            print("Error reading memory limit from cgroups v1")
            pass
            
        # Check environment variables that Render might set
        if 'MEMORY_LIMIT' in os.environ:
            return int(os.environ['MEMORY_LIMIT']) * 1024 * 1024  # Assume MB
        
        # Default to Render free tier limit
        print("Warning: Could not detect container memory limit, assuming 512MB")
        return 512 * 1024 * 1024  # 512MB in bytes
        
    except Exception as e:
        print(f"Error detecting memory limit: {e}")
        return 512 * 1024 * 1024  # Default to 512MB

def get_container_memory_usage():
    """Get current memory usage that respects container limits"""
    try:
        # First try to read current usage from cgroups v2 (most accurate for containers)
        try:
            with open('/sys/fs/cgroup/memory.current', 'r') as f:
                cgroup_memory = int(f.read().strip())
                print(f"Container memory from cgroups v2: {cgroup_memory/(1024*1024):.1f}MB")
                return cgroup_memory
        except Exception as e:
            print(f"Error reading memory usage from cgroups v2: {e}")
        
        # Try to read current usage from cgroups v1
        try:
            with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
                cgroup_memory = int(f.read().strip())
                print(f"Container memory from cgroups v1: {cgroup_memory/(1024*1024):.1f}MB")
                return cgroup_memory
        except Exception as e:
            print(f"Error reading memory usage from cgroups v1: {e}")
        
        # Fallback to process memory (less accurate but better than system memory)
        current_process = psutil.Process()
        process_memory = current_process.memory_info()
        
        # RSS (Resident Set Size) is the actual physical memory used by this process
        actual_memory_used = process_memory.rss
        
        print(f"Process memory fallback - RSS: {actual_memory_used/(1024*1024):.1f}MB, VMS: {process_memory.vms/(1024*1024):.1f}MB")
        return actual_memory_used
        
    except Exception as e:
        print(f"Error reading container memory: {e}")
        # Final fallback to system memory (least accurate)
        memory = psutil.virtual_memory()
        print("Using system memory as final fallback")
        return memory.used

def log_memory_usage(stage):
    """Log current memory usage with container awareness and peak tracking"""
    global _peak_memory_usage
    
    try:
        memory_limit = get_container_memory_limit()
        memory_used = get_container_memory_usage()
        memory_percent = (memory_used / memory_limit) * 100
        
        # Track peak memory usage
        if memory_used > _peak_memory_usage:
            _peak_memory_usage = memory_used
            
        print(f"Memory at {stage}: {memory_percent:.1f}% used ({memory_used/(1024*1024):.1f}MB/{memory_limit/(1024*1024):.1f}MB) [Peak: {_peak_memory_usage/(1024*1024):.1f}MB]")
        return memory_percent
    except Exception as e:
        print(f"Error in memory logging: {e}")
        # Fallback to psutil
        memory = psutil.virtual_memory()
        print(f"Memory at {stage}: {memory.percent}% used ({memory.used/(1024*1024):.1f}MB/{memory.total/(1024*1024):.1f}MB) [HOST]")
        return memory.percent



def extract_text_from_pdf_memory(file_obj, filename=""):
    """Extract text from a PDF file object directly from memory with OCR fallback"""
    final_text = ""
    ocr_pages_count = 0  # Track how many pages needed OCR
    
    try:
        analyze_memory_usage(f"PDF extraction start - {filename}")
        
        # Reset file pointer to beginning
        file_obj.seek(0)
        
        # Create PDF reader from file object
        pdf_reader = PyPDF2.PdfReader(file_obj)
        num_pages = len(pdf_reader.pages)
        
        print(f"Processing PDF '{filename}' with {num_pages} pages from memory")
        
        # Process pages in smaller batches to reduce memory usage
        batch_size = 5 if num_pages > 20 else 10  # Smaller batches for large files
        
        for batch_start in range(0, num_pages, batch_size):
            batch_end = min(batch_start + batch_size, num_pages)
            batch_text = ""
            
            print(f"Processing batch: pages {batch_start + 1}-{batch_end}")
            
            for page_num in range(batch_start, batch_end):
                print(f"Extracting text from page {page_num + 1}")
                
                # Check memory before processing each page
                check_memory()
                
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text().strip()
                
                # Check if extracted text is insufficient (less than configured threshold)
                if len(page_text) < OCR_TEXT_THRESHOLD:
                    if OCR_AVAILABLE:
                        print(f"Page {page_num + 1}: Insufficient text ({len(page_text)} chars), trying OCR...")
                        
                        try:
                            # Use OCR directly on PDF page
                            ocr_text = extract_text_with_ocr_from_pdf(file_obj, page_num).strip()
                            
                            # Use OCR text if it's significantly better
                            if len(ocr_text) > len(page_text):
                                print(f"Page {page_num + 1}: OCR extracted {len(ocr_text)} chars (vs {len(page_text)} from PDF)")
                                print("OCR text ***")
                                print(ocr_text[:100])
                                page_text = ocr_text
                                ocr_pages_count += 1
                            else:
                                print(f"Page {page_num + 1}: OCR didn't improve text extraction ({len(ocr_text)} chars)")
                                
                        except Exception as ocr_error:
                            print(f"Page {page_num + 1}: OCR failed - {str(ocr_error)}")
                    else:
                        print(f"Page {page_num + 1}: Insufficient text ({len(page_text)} chars), but OCR not available")
                else:
                    print(f"Page {page_num + 1}: Good text extraction ({len(page_text)} chars)")
                
                # Add page text to batch
                batch_text += f"[Page {page_num + 1}]:\n{page_text}\n\n"
                
                # Clear page reference to help garbage collection
                del page_text
                del page
                
                # Force garbage collection and check effect
                gc.collect()
            
            # Add batch to final text and clear batch
            final_text += batch_text
            del batch_text
            
            # Force garbage collection between batches for large files
            if num_pages > 15:
                gc.collect()
        
        # Log OCR usage statistics
        if ocr_pages_count > 0:
            print(f"OCR was used on {ocr_pages_count}/{num_pages} pages ({ocr_pages_count/num_pages*100:.1f}%)")
        elif OCR_AVAILABLE:
            print(f"All {num_pages} pages had sufficient text, no OCR needed")
        else:
            insufficient_pages = sum(1 for page_num in range(num_pages) 
                                   if len(pdf_reader.pages[page_num].extract_text().strip()) < OCR_TEXT_THRESHOLD)
            if insufficient_pages > 0:
                print(f"Note: {insufficient_pages}/{num_pages} pages had insufficient text but OCR was unavailable")
            else:
                print(f"All {num_pages} pages had sufficient text (OCR not needed)")
        
        analyze_memory_usage(f"PDF extraction complete - {filename}")
        return final_text.strip()
        
    except Exception as e:
        print(f"Error extracting text from PDF in memory: {str(e)}")
        analyze_memory_usage(f"PDF extraction error - {filename}")
        # Force cleanup on error
        gc.collect()
        return ""

def set_process_priority():
    """Configure process priority based on OS"""
    current_process = psutil.Process()
    try:
        if platform.system() == 'Windows':
            current_process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            current_process.nice(10)  # Unix-like systems
    except:
        print("Could not set process priority")

def check_memory():
    """Check if system has enough memory with proactive garbage collection and container awareness"""
    try:
        memory_limit = get_container_memory_limit()
        memory_used = get_container_memory_usage()
        memory_percent = (memory_used / memory_limit) * 100
        
        if memory_percent > 75:  # Lower threshold for containers (was 85%)
            print(f"High memory usage detected: {memory_percent:.1f}% - forcing garbage collection")
            gc.collect()  # Force garbage collection
            
            # Check again after garbage collection
            memory_used = get_container_memory_usage()
            memory_percent = (memory_used / memory_limit) * 100
            print(f"Memory after GC: {memory_percent:.1f}%")
            
        if memory_percent > 90:  # Critical threshold for containers (was 95%)
            print(f"Memory usage critical: {memory_percent:.1f}% ({memory_used/(1024*1024):.1f}MB/{memory_limit/(1024*1024):.1f}MB)")
        
        return memory_percent
        
    except Exception as e:
        if "Memory usage critical" in str(e):
            raise  # Re-raise critical memory errors
        
        print(f"Error in container memory check: {e}")
        # Fallback to psutil
        memory = psutil.virtual_memory()
        
        if memory.percent > 85:
            print(f"High memory usage detected (host): {memory.percent}% - forcing garbage collection")
            gc.collect()
            memory = psutil.virtual_memory()
            
        if memory.percent > 95:
            print(f"Memory usage critical (host): {memory.percent}%")
        
        return memory.percent

def analyze_memory_usage(stage):
    """Detailed memory analysis to identify memory consumers"""
    try:
        current_process = psutil.Process()
        memory_info = current_process.memory_info()
        memory_percent = current_process.memory_percent()
        
        # Get number of open file descriptors
        try:
            num_fds = current_process.num_fds()
        except:
            num_fds = "N/A"
        
        # Get thread count
        num_threads = current_process.num_threads()
        
        # Try to get container memory for comparison
        container_memory = None
        try:
            with open('/sys/fs/cgroup/memory.current', 'r') as f:
                container_memory = int(f.read().strip())
        except:
            try:
                with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
                    container_memory = int(f.read().strip())
            except:
                pass
        
        print(f"=== Memory Analysis at {stage} ===")
        print(f"Process RSS (Physical): {memory_info.rss/(1024*1024):.1f}MB")
        print(f"Process VMS (Virtual): {memory_info.vms/(1024*1024):.1f}MB")
        if container_memory:
            print(f"Container Memory (cgroups): {container_memory/(1024*1024):.1f}MB")
            print(f"Difference (Container - Process): {(container_memory - memory_info.rss)/(1024*1024):.1f}MB")
        print(f"Memory %: {memory_percent:.1f}%")
        print(f"Threads: {num_threads}")
        print(f"File descriptors: {num_fds}")
        
        # Check for memory leaks by looking at object counts
        import sys
        print(f"Python objects: {len(gc.get_objects())}")
        
        # Return container memory if available, otherwise process memory
        return container_memory if container_memory else memory_info.rss
        
    except Exception as e:
        print(f"Error in memory analysis: {e}")
        return 0
