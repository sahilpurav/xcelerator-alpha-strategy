#!/usr/bin/env python3
"""
Temporary script to extract stock symbols from Nifty 500 PDF files.
This script handles text-based PDFs and cleans up formatting issues.
"""

import PyPDF2
import sys
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    """Extract raw text from PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None

def clean_and_extract_symbols(text):
    """
    Extract stock symbols from the PDF text.
    Handles various formatting issues like extra spaces, line breaks, concatenation, etc.
    """
    if not text:
        return []
    
    # Split text into lines and clean up
    lines = text.split('\n')
    
    symbols = []
    
    # More specific pattern for stock symbols (typically appear in a tabular format)
    for line in lines:
        # Clean the line
        cleaned_line = ' '.join(line.split())
        if not cleaned_line:
            continue
            
        # Skip obvious header/footer lines
        if any(skip_word in cleaned_line.upper() for skip_word in [
            'NIFTY', 'INDEX', 'PAGE', 'COMPANY', 'SYMBOL', 'SECTOR', 
            'MARKET', 'CAP', 'WEIGHTAGE', 'SR.', 'S.NO', 'DATE',
            'NATIONAL STOCK EXCHANGE', 'WWW.', 'HTTP', 'CLASSIFICATION',
            'CLOSE PRICE', 'SECURITY NAME', 'INDUSTRY', 'RS. CRORES'
        ]):
            continue
        
        # Handle concatenated symbols (e.g., "ADANIPORTSAdani Ports..." or "JBCHEPHARMJ.B.")
        # Look for pattern: UPPERCASETEXT followed by Titlecase or abbreviations with periods
        import re
        
        # First, try to match concatenated patterns with more sophisticated logic
        # Pattern 1: Symbol followed by company name starting with uppercase + lowercase
        concat_match1 = re.match(r'^([A-Z0-9&-]{3,15})([A-Z][a-z].*)', cleaned_line)
        
        # Pattern 2: Symbol followed by abbreviated name with periods (like J.B.)
        concat_match2 = re.match(r'^([A-Z0-9&-]{3,15})([A-Z]\.[A-Z]\..*)', cleaned_line)
        
        # Pattern 3: More general - symbol followed by any non-alphanumeric or mixed case
        concat_match3 = re.match(r'^([A-Z0-9&-]{3,15})([^A-Z0-9].*|[A-Z][a-z])', cleaned_line)
        
        concatenated_match = concat_match1 or concat_match2 or concat_match3
        
        if concatenated_match:
            potential_symbol = concatenated_match.group(1)
            remaining_text = concatenated_match.group(2)
            
            # Debug output for POWERINDIAABB case
            if 'POWERINDIA' in potential_symbol:
                print(f"DEBUG: Found POWERINDIA case: '{potential_symbol}' + '{remaining_text}'")
            
            # Additional validation: ensure it doesn't end with periods or invalid chars
            potential_symbol = potential_symbol.rstrip('.')
            
            # Special case handling for known problematic concatenations (apply first)
            concatenation_fixes = {
                'POWERINDIAABB': 'POWERINDIA',
                'ICICIGIICICI': 'ICICIGI', 
                'ICICIPRULIICICI': 'ICICIPRULI',
                'ADANIPORTSAdani': 'ADANIPORTS',
                'HDFCBANKHDFC': 'HDFCBANK',
                'IL&FSTRANSIL&FS': 'IL&FSTRANS',
                'HDFCLIFEHDFC': 'HDFCLIFE',
                'MINDTREE': 'LTIM',
                'GRMINFRA': 'GMRINFRA-EQ'
            }
            was_concatenation_fixed = False
            if potential_symbol in concatenation_fixes:
                print(f"DEBUG: Applying concatenation fix: {potential_symbol} -> {concatenation_fixes[potential_symbol]}")
                potential_symbol = concatenation_fixes[potential_symbol]
                was_concatenation_fixed = True
            
            # Check for company name pattern in remaining text to detect over-extraction
            # Common patterns that indicate we've captured too much:
            company_patterns = [
                r'^\s*(Power Products|Lombard|Prudential|General Insurance|Life Insurance)',
                r'^\s*(India Ltd|Limited|Corp|Corporation)',
                r'^\s*[A-Z][a-z]+ (Ltd|Limited|Corporation|Insurance|Bank)',
            ]
            
            # If remaining text starts with a company name pattern, try to trim the symbol
            # BUT SKIP this if we already applied a concatenation fix (those are manually verified)
            symbol_was_trimmed = False
            if not was_concatenation_fixed:
                for pattern in company_patterns:
                    if re.match(pattern, remaining_text):
                        print(f"DEBUG: Found company pattern '{pattern}' in remaining text: '{remaining_text}' for symbol: '{potential_symbol}'")
                        # Try to find a better break point in the symbol
                        # Look for known symbol endings that got concatenated with company names
                        known_endings = ['ABB', 'ICICI', 'HDFC', 'TATA', 'INDIA']
                        for ending in known_endings:
                            if potential_symbol.endswith(ending) and len(potential_symbol) > len(ending):
                                # Check if trimming this ending gives us a valid symbol
                                trimmed_symbol = potential_symbol[:-len(ending)]
                                if len(trimmed_symbol) >= 3:
                                    print(f"DEBUG: Trimming '{ending}' from '{potential_symbol}' -> '{trimmed_symbol}'")
                                    potential_symbol = trimmed_symbol
                                    symbol_was_trimmed = True
                                    break
                        break
            
            # Filter out obvious concatenation artifacts
            # Check for repetitive patterns like "ICICIGIICICI" or overly long symbols with company name parts
            is_repetitive = any(part * 2 in potential_symbol for part in ['ICICI', 'HDFC', 'BAJAJ', 'TATA', 'BIRLA'])
            has_company_suffix = any(potential_symbol.endswith(suffix) for suffix in ['LTD', 'LIMITED', 'CORP'])
            # Note: 'INDIA' removed from suffix check as legitimate symbols can end with INDIA (like POWERINDIA)
            
            # Validate the extracted symbol
            if (len(potential_symbol) >= 2 and 
                len(potential_symbol) <= 15 and 
                not potential_symbol.isdigit() and
                not potential_symbol.startswith('PUBLICATION') and
                not is_repetitive and
                not has_company_suffix and
                potential_symbol not in ['NSE', 'INR', 'RS', 'CRORE', 'LAKH', 'TOTAL']):
                symbols.append(potential_symbol)
                continue
        
        # Standard processing: Look for symbol-company format with spaces
        words = cleaned_line.split()
        
        if len(words) >= 2:  # At least symbol + company name
            potential_symbol = words[0]
            
            # Validate potential symbol
            if (len(potential_symbol) >= 2 and 
                len(potential_symbol) <= 15 and 
                potential_symbol.isupper() and
                not potential_symbol.isdigit() and
                potential_symbol not in ['NSE', 'INR', 'RS', 'CRORE', 'LAKH', 'TOTAL', 'PUBLICATION']):
                
                # Additional check: next words should look like company name (mixed case or all caps)
                company_part = ' '.join(words[1:])
                if len(company_part) > 3:  # Company name should be reasonably long
                    symbols.append(potential_symbol)
    
    # Remove duplicates while preserving order
    unique_symbols = []
    seen = set()
    for symbol in symbols:
        if symbol not in seen:
            unique_symbols.append(symbol)
            seen.add(symbol)
    
    return unique_symbols

def manual_extraction_mode():
    """
    Fallback mode: provide instructions for manual extraction.
    """
    print("\n" + "="*60)
    print("MANUAL EXTRACTION MODE")
    print("="*60)
    print("If automatic extraction doesn't work well, follow these steps:")
    print("1. Copy text from the PDF")
    print("2. Paste it below (press Ctrl+D or Ctrl+Z when done)")
    print("3. The script will clean and extract symbols")
    print("-"*60)
    
    try:
        print("Paste the copied text here:")
        text_input = sys.stdin.read()
        return clean_and_extract_symbols(text_input)
    except KeyboardInterrupt:
        print("\nManual extraction cancelled.")
        return []

def debug_text_extraction(pdf_path, save_raw=False):
    """Debug function to examine raw text extraction."""
    text = extract_text_from_pdf(pdf_path)
    
    # Analyze text structure
    if text:
        lines = text.split('\n')
        print(f"Total lines in PDF: {len(lines)}")
        print(f"Non-empty lines: {len([l for l in lines if l.strip()])}")
        
        # Look for patterns that might indicate symbols
        potential_symbols = []
        for line in lines:
            words = line.split()
            if words:
                first_word = words[0].strip()
                if (len(first_word) >= 2 and 
                    len(first_word) <= 15 and 
                    first_word.isupper() and 
                    not first_word.isdigit()):
                    potential_symbols.append(first_word)
        
        print(f"Potential symbols found: {len(set(potential_symbols))}")
        return text, potential_symbols
    
    return None, []

def main():
    """Main function to extract symbols from PDF."""
    
    # Check if PDF path is provided
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default to the attached PDF
        pdf_path = "assets/nifty-500-historical-constituents/nifty500_Oct2017.pdf"
    
    pdf_file = Path(pdf_path)
    
    if not pdf_file.exists():
        print(f"Error: PDF file '{pdf_path}' not found.")
        print("Available PDF files:")
        pdf_dir = Path("assets/nifty-500-historical-constituents/")
        if pdf_dir.exists():
            for pdf in pdf_dir.glob("*.pdf"):
                print(f"  {pdf}")
        return
    
    print(f"Extracting symbols from: {pdf_file}")
    print("-" * 50)
    
    # Debug: Analyze raw text first
    print("\nDEBUG: Analyzing raw text extraction...")
    debug_text_extraction(pdf_file, save_raw=False)
    print("-" * 50)
    
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_file)
    
    if text:
        # Extract symbols
        symbols = clean_and_extract_symbols(text)
        
        if symbols:
            print(f"Found {len(symbols)} symbols:")
            print("-" * 30)
            
            # Print symbols in columns for better readability
            cols = 4
            for i in range(0, len(symbols), cols):
                row_symbols = symbols[i:i+cols]
                print("  ".join(f"{sym:<12}" for sym in row_symbols))
            
            # Save to output folder
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            output_file = output_dir / (pdf_file.stem + "_symbols.txt")
            with open(output_file, 'w') as f:
                for symbol in symbols:
                    f.write(symbol + '\n')
            
            print(f"\nSymbols saved to: {output_file}")
            
        else:
            print("No symbols found with automatic extraction.")
            print("Trying manual extraction mode...")
            symbols = manual_extraction_mode()
            
            if symbols:
                print(f"Manually extracted {len(symbols)} symbols:")
                for i, symbol in enumerate(symbols, 1):
                    print(f"{i:3d}. {symbol}")
    else:
        print("Failed to extract text from PDF.")
        print("Trying manual extraction mode...")
        symbols = manual_extraction_mode()

if __name__ == "__main__":
    main()
