"""
OCR & Text Extraction
Extract and read text from screen, logs, and images
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image
import io
import re

class OCRTextExtractor:
    """Extracts text from images and screen using OCR"""
    
    def __init__(self):
        self.extracted_cache = {}
        self.ocr_engine = None
        self._initialize_ocr()
    
    def _initialize_ocr(self):
        """Initialize OCR engine"""
        try:
            import pytesseract
            self.ocr_engine = pytesseract
            self.use_tesseract = True
        except ImportError:
            print("Tesseract not found, using fallback OCR")
            self.use_tesseract = False
    
    async def extract_text_from_image(self, image: Image.Image,
                                     language: str = 'eng') -> Dict[str, Any]:
        """
        Extract all text from an image
        
        Args:
            image: PIL Image to extract text from
            language: OCR language (eng, fra, deu, etc)
        
        Returns:
            Extracted text and metadata
        """
        result = {
            "raw_text": "",
            "lines": [],
            "confidence": 0.0,
            "language": language,
            "text_blocks": []
        }
        
        try:
            if self.use_tesseract:
                import pytesseract
                
                # Extract text with detailed data
                data = pytesseract.image_to_data(image, lang=language, output_type=pytesseract.Output.DICT)
                
                result["raw_text"] = pytesseract.image_to_string(image, lang=language)
                result["confidence"] = np.mean([int(c) for c in data['confidence'] if c != '-1']) if data['confidence'] else 0
                
                # Group text into lines
                current_line = ""
                current_y = -1
                
                for i, text in enumerate(data['text']):
                    if text.strip():
                        if data['top'][i] != current_y and current_line:
                            result["lines"].append(current_line)
                            current_line = text
                            current_y = data['top'][i]
                        else:
                            if current_line:
                                current_line += " " + text
                            else:
                                current_line = text
                            current_y = data['top'][i]
                
                if current_line:
                    result["lines"].append(current_line)
                
                # Extract text blocks
                for i, text in enumerate(data['text']):
                    if text.strip():
                        result["text_blocks"].append({
                            "text": text,
                            "x": data['left'][i],
                            "y": data['top'][i],
                            "width": data['width'][i],
                            "height": data['height'][i],
                            "confidence": int(data['confidence'][i])
                        })
            
            else:
                result["raw_text"] = await self._fallback_ocr(image)
                result["lines"] = result["raw_text"].split('\n')
        
        except Exception as e:
            result["error"] = str(e)
            result["raw_text"] = ""
        
        return result
    
    async def _fallback_ocr(self, image: Image.Image) -> str:
        """Fallback OCR using simple pattern matching"""
        # This is a basic fallback - proper implementation would use EasyOCR
        try:
            import easyocr
            reader = easyocr.Reader(['en'])
            result = reader.readtext(image)
            text = '\n'.join([detection[1] for detection in result])
            return text
        except:
            return "[Tesseract and EasyOCR not available]"
    
    async def extract_error_messages(self, image: Image.Image) -> List[str]:
        """Extract error messages from screen"""
        text_result = await self.extract_text_from_image(image)
        raw_text = text_result["raw_text"]
        
        errors = []
        
        # Common error patterns
        error_patterns = [
            r'(?:Error|ERROR|Error:).*',
            r'(?:Exception|EXCEPTION).*',
            r'(?:Failed|FAILED).*',
            r'(?:Cannot|CAN\'T).*',
            r'(?:Not found|NOT FOUND).*',
            r'(?:Invalid|INVALID).*',
            r'Traceback.*',
            r'(?:Warning|WARNING).*',
            r'(?:Critical|CRITICAL).*'
        ]
        
        for pattern in error_patterns:
            matches = re.findall(pattern, raw_text, re.MULTILINE)
            errors.extend(matches)
        
        return list(set(errors))  # Remove duplicates
    
    async def extract_code_from_screen(self, image: Image.Image) -> Dict[str, Any]:
        """Extract code/programming text from screen"""
        text_result = await self.extract_text_from_image(image)
        raw_text = text_result["raw_text"]
        
        result = {
            "code_blocks": [],
            "programming_languages": [],
            "function_definitions": [],
            "variables": []
        }
        
        # Detect programming language patterns
        lang_patterns = {
            "python": [r'def \w+\(', r'import \w+', r'class \w+:'],
            "javascript": [r'function \w+\(', r'const \w+\s*=', r'import.*from'],
            "java": [r'public class', r'public static void', r'private \w+ \w+'],
            "cpp": [r'int main\(\)', r'#include', r'std::'],
            "csharp": [r'public class', r'using', r'namespace'],
        }
        
        for lang, patterns in lang_patterns.items():
            for pattern in patterns:
                if re.search(pattern, raw_text):
                    result["programming_languages"].append(lang)
                    break
        
        # Extract function/method definitions
        func_pattern = r'(?:def|function|public|private|void|class)\s+(\w+)'
        result["function_definitions"] = re.findall(func_pattern, raw_text)
        
        # Extract variable assignments
        var_pattern = r'(\w+)\s*(?:=|:=)\s*'
        result["variables"] = re.findall(var_pattern, raw_text)[:20]  # Limit to 20
        
        # Code blocks (indented text)
        lines = raw_text.split('\n')
        current_block = ""
        for line in lines:
            if line.startswith(('    ', '\t')) or re.match(r'^\s{2,}', line):
                current_block += line + '\n'
            elif current_block:
                result["code_blocks"].append(current_block.strip())
                current_block = ""
        
        if current_block:
            result["code_blocks"].append(current_block.strip())
        
        return result
    
    async def extract_table_data(self, image: Image.Image) -> Dict[str, Any]:
        """Extract table/structured data from image"""
        result = {
            "table_detected": False,
            "rows": [],
            "columns": [],
            "data": []
        }
        
        try:
            text_result = await self.extract_text_from_image(image)
            blocks = text_result["text_blocks"]
            
            if not blocks:
                return result
            
            # Group text blocks by vertical position (rows)
            rows_by_y = {}
            for block in blocks:
                y = block["y"]
                # Group similar Y positions
                found_row = False
                for row_y in rows_by_y:
                    if abs(y - row_y) < 20:
                        rows_by_y[row_y].append(block)
                        found_row = True
                        break
                
                if not found_row:
                    rows_by_y[y] = [block]
            
            # Sort rows by Y position
            sorted_rows = sorted(rows_by_y.items(), key=lambda x: x[0])
            
            if len(sorted_rows) > 2:
                result["table_detected"] = True
                
                for row_y, blocks_in_row in sorted_rows:
                    # Sort blocks by X position
                    blocks_in_row.sort(key=lambda b: b["x"])
                    row_data = [b["text"] for b in blocks_in_row]
                    result["rows"].append(row_data)
                
                # Extract columns
                if result["rows"]:
                    result["columns"] = result["rows"][0]
                    result["data"] = result["rows"][1:]
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def read_log_file(self, file_path: str,
                           search_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Read and analyze a log file
        
        Args:
            file_path: Path to log file
            search_patterns: Optional list of patterns to search for
        
        Returns:
            Log analysis result
        """
        result = {
            "total_lines": 0,
            "errors": [],
            "warnings": [],
            "matches": [],
            "last_entries": []
        }
        
        try:
            with open(file_path, 'r', errors='ignore') as f:
                lines = f.readlines()
            
            result["total_lines"] = len(lines)
            result["last_entries"] = lines[-10:] if len(lines) > 10 else lines
            
            # Search for errors and warnings
            for line in lines:
                if 'ERROR' in line or 'Error' in line:
                    result["errors"].append(line.strip())
                elif 'WARNING' in line or 'Warning' in line:
                    result["warnings"].append(line.strip())
            
            # Search for custom patterns
            if search_patterns:
                for pattern in search_patterns:
                    for line in lines:
                        if re.search(pattern, line):
                            result["matches"].append({
                                "pattern": pattern,
                                "line": line.strip()
                            })
            
            # Limit results
            result["errors"] = result["errors"][-20:]
            result["warnings"] = result["warnings"][-20:]
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def extract_urls(self, image: Image.Image) -> List[str]:
        """Extract URLs from screen text"""
        text_result = await self.extract_text_from_image(image)
        raw_text = text_result["raw_text"]
        
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, raw_text)
        
        return list(set(urls))  # Remove duplicates
    
    async def extract_email_addresses(self, image: Image.Image) -> List[str]:
        """Extract email addresses from screen"""
        text_result = await self.extract_text_from_image(image)
        raw_text = text_result["raw_text"]
        
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, raw_text)
        
        return list(set(emails))
    
    async def extract_phone_numbers(self, image: Image.Image) -> List[str]:
        """Extract phone numbers from screen"""
        text_result = await self.extract_text_from_image(image)
        raw_text = text_result["raw_text"]
        
        phone_patterns = [
            r'\+?1?\d{3}[-.]?\d{3}[-.]?\d{4}',  # US/International
            r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',      # (XXX) XXX-XXXX
            r'\d{3}\s\d{3}\s\d{4}'                # XXX XXX XXXX
        ]
        
        phones = []
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, raw_text))
        
        return list(set(phones))
    
    async def highlight_text_on_image(self, image: Image.Image, 
                                     search_text: str) -> Image.Image:
        """Highlight found text on image"""
        try:
            from PIL import ImageDraw
            
            text_result = await self.extract_text_from_image(image)
            blocks = text_result["text_blocks"]
            
            annotated = image.copy()
            draw = ImageDraw.Draw(annotated)
            
            for block in blocks:
                if search_text.lower() in block["text"].lower():
                    x = block["x"]
                    y = block["y"]
                    w = block["width"]
                    h = block["height"]
                    
                    # Draw highlight
                    draw.rectangle([(x, y), (x + w, y + h)], outline=(0, 255, 255), width=2)
            
            return annotated
        
        except:
            return image


import numpy as np
