"""
File type filtering for DocuSense
Prevents downloading files that won't extract meaningful text
Reduces bandwidth costs and processing time
"""

import logging
from typing import Tuple, Optional

# Supported MIME types that can extract meaningful text
SUPPORTED_MIME_TYPES = {
    # Microsoft Office Documents
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',        # .xlsx
    'application/vnd.openxmlformats-officedocument.presentationml.presentation', # .pptx
    'application/msword',                                                        # .doc
    'application/vnd.ms-excel',                                                  # .xls
    'application/vnd.ms-powerpoint',                                            # .ppt
    
    # PDF Documents
    'application/pdf',
    
    # Text Files
    'text/plain',
    'text/csv',
    'text/html',
    'text/xml',
    'application/xml',
    'text/markdown',
    'text/rtf',
    'application/rtf',
    
    # Other Document Formats
    'application/vnd.oasis.opendocument.text',          # .odt
    'application/vnd.oasis.opendocument.spreadsheet',   # .ods
    'application/vnd.oasis.opendocument.presentation',  # .odp
}

# File extensions to skip (binary files that won't extract text)
SKIP_EXTENSIONS = {
    # Archives
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
    
    # Media Files
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',  # Video
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', # Audio
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg', '.webp', # Images
    
    # Executables and System Files
    '.exe', '.msi', '.deb', '.rpm', '.dmg', '.pkg',
    '.dll', '.so', '.dylib',
    
    # CAD and Design Files
    '.dwg', '.dxf', '.3ds', '.blend', '.max',
    
    # Database Files
    '.db', '.sqlite', '.mdb', '.accdb',
    
    # Temporary/Cache Files
    '.tmp', '.temp', '.cache', '.log',
}

def should_process_file(file_name: str, mime_type: Optional[str], file_size: int) -> Tuple[bool, str]:
    """
    Determine if a file should be processed based on type and size
    
    Args:
        file_name: Name of the file
        mime_type: MIME type from Graph API (can be None)
        file_size: Size in bytes
        
    Returns:
        Tuple of (should_process, reason)
    """
    
    # Check file extension for obvious skips
    file_name_lower = file_name.lower()
    for skip_ext in SKIP_EXTENSIONS:
        if file_name_lower.endswith(skip_ext):
            return False, f"Skipped binary file type: {skip_ext}"
    
    # Check MIME type if available
    if mime_type:
        if mime_type in SUPPORTED_MIME_TYPES:
            return True, f"Supported MIME type: {mime_type}"
        
        # Check for generic text types
        if mime_type.startswith('text/'):
            return True, f"Text file: {mime_type}"
        
        # Skip known binary types
        binary_prefixes = ['image/', 'video/', 'audio/', 'application/octet-stream']
        for prefix in binary_prefixes:
            if mime_type.startswith(prefix):
                return False, f"Binary MIME type: {mime_type}"
    
    # Fallback: check common text file extensions
    text_extensions = {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm', '.rtf'}
    for ext in text_extensions:
        if file_name_lower.endswith(ext):
            return True, f"Text file extension: {ext}"
    
    # If no MIME type and unknown extension, be conservative for large files
    if file_size > 10 * 1024 * 1024:  # 10MB
        return False, f"Unknown file type and large size ({file_size} bytes), skipping to save bandwidth"
    
    # Small unknown files - process them (might be text without extension)
    return True, f"Small unknown file ({file_size} bytes), processing"

def get_estimated_processing_cost(file_size: int, file_type: str = "pdf") -> float:
    """
    Estimate the embedding cost for processing a file
    
    Args:
        file_size: File size in bytes
        file_type: Type of file (affects text density)
        
    Returns:
        Estimated cost in USD
    """
    
    # Rough estimates of text extraction ratios
    text_ratios = {
        "pdf": 0.15,      # PDFs are ~15% text by size
        "docx": 0.10,     # Word docs have more formatting overhead
        "pptx": 0.05,     # PowerPoints are mostly formatting/images
        "txt": 1.0,       # Plain text is 100% text
        "default": 0.10   # Conservative default
    }
    
    ratio = text_ratios.get(file_type.lower(), text_ratios["default"])
    estimated_text_size = file_size * ratio
    
    # Rough conversion: 1 byte ≈ 0.25 tokens (English text)
    estimated_tokens = estimated_text_size * 0.25
    
    # Azure OpenAI embedding cost: $0.0001 per 1K tokens
    cost_per_1k_tokens = 0.0001
    estimated_cost = (estimated_tokens / 1000) * cost_per_1k_tokens
    
    return estimated_cost

def log_file_decision(file_name: str, file_size: int, mime_type: Optional[str], 
                     should_process: bool, reason: str):
    """
    Log the file processing decision with cost estimates
    """
    
    size_mb = file_size / (1024 * 1024)
    
    if should_process:
        # Estimate processing cost
        file_ext = file_name.split('.')[-1].lower() if '.' in file_name else 'default'
        estimated_cost = get_estimated_processing_cost(file_size, file_ext)
        
        logging.info(f'✅ PROCESSING: {file_name} ({size_mb:.1f}MB, {mime_type}) - {reason} - Est. cost: ${estimated_cost:.4f}')
    else:
        logging.info(f'⏭️  SKIPPING: {file_name} ({size_mb:.1f}MB, {mime_type}) - {reason}')

def check_search_index_capacity(current_docs: int, estimated_new_chunks: int) -> Tuple[bool, str]:
    """
    Check if adding new document chunks would exceed search index limits
    
    Args:
        current_docs: Current number of documents in index
        estimated_new_chunks: Estimated chunks from new file
        
    Returns:
        Tuple of (can_add, message)
    """
    
    # Azure AI Search limits (ChatGPT recommendation)
    search_limits = {
        "free": 10000,        # Free tier: 10K docs
        "basic": 1000000,     # Basic: 1M docs  
        "s1": 15000000,       # S1: 15M docs, ~10GB storage
        "s2": 60000000,       # S2: 60M docs, ~100GB storage
    }
    
    # Assume S1 tier for now (can be configured)
    current_tier = "s1"
    max_docs = search_limits[current_tier]
    
    projected_total = current_docs + estimated_new_chunks
    
    if projected_total > max_docs * 0.9:  # 90% threshold warning
        return False, f"Search index near capacity: {projected_total}/{max_docs} docs (tier: {current_tier})"
    
    return True, f"Search index capacity OK: {projected_total}/{max_docs} docs" 