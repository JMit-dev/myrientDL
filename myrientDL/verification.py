import zipfile
import zlib
from typing import Optional, Tuple
from pathlib import Path
import re


class TorrentZipVerifier:
    """Verify and extract information from TorrentZip archives"""

    @staticmethod
    def is_torrentzipped(zip_path: Path) -> bool:
        """Check if a ZIP file is TorrentZipped"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                comment = zf.comment.decode('utf-8', errors='ignore')
                return comment.startswith('TORRENTZIPPED-')
        except Exception:
            return False

    @staticmethod
    def get_torrentzip_crc32(zip_path: Path) -> Optional[str]:
        """Extract CRC-32 from TorrentZip comment"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                comment = zf.comment.decode('utf-8', errors='ignore')
                match = re.match(r'TORRENTZIPPED-([0-9A-Fa-f]{8})', comment)
                if match:
                    return match.group(1).upper()
        except Exception:
            pass
        return None

    @staticmethod
    def verify_torrentzip_crc32(zip_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Verify TorrentZip CRC-32 checksum

        Returns:
            Tuple of (is_valid, crc32_hash)
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Get comment CRC-32
                comment = zf.comment.decode('utf-8', errors='ignore')
                match = re.match(r'TORRENTZIPPED-([0-9A-Fa-f]{8})', comment)
                if not match:
                    return False, None

                expected_crc = match.group(1).upper()

                # Calculate CRC-32 of central directory
                # TorrentZip CRC is the CRC of all file entries in central directory
                crc = 0
                for info in zf.infolist():
                    # Get raw central directory data for this file
                    # CRC is calculated on filename + extra + comment
                    file_data = info.filename.encode('utf-8')
                    crc = zlib.crc32(file_data, crc)

                calculated_crc = format(crc & 0xFFFFFFFF, '08X')

                return calculated_crc == expected_crc, calculated_crc

        except Exception:
            return False, None

    @staticmethod
    def get_archive_info(zip_path: Path) -> dict:
        """
        Get detailed information about a ZIP archive

        Returns dict with:
            - is_torrentzipped: bool
            - torrentzip_crc32: Optional[str]
            - num_files: int
            - total_uncompressed_size: int
            - file_list: list of file names
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                is_tz = False
                tz_crc = None

                comment = zf.comment.decode('utf-8', errors='ignore')
                if comment.startswith('TORRENTZIPPED-'):
                    is_tz = True
                    match = re.match(r'TORRENTZIPPED-([0-9A-Fa-f]{8})', comment)
                    if match:
                        tz_crc = match.group(1).upper()

                file_list = [info.filename for info in zf.infolist() if not info.is_dir()]
                total_size = sum(info.file_size for info in zf.infolist() if not info.is_dir())

                return {
                    'is_torrentzipped': is_tz,
                    'torrentzip_crc32': tz_crc,
                    'num_files': len(file_list),
                    'total_uncompressed_size': total_size,
                    'file_list': file_list,
                    'archive_comment': comment
                }

        except Exception as e:
            return {
                'error': str(e),
                'is_torrentzipped': False,
                'torrentzip_crc32': None,
                'num_files': 0,
                'total_uncompressed_size': 0,
                'file_list': []
            }


class ChecksumVerifier:
    """Verify file checksums against known databases"""

    @staticmethod
    def verify_file_checksum(file_path: Path, expected_checksum: str, checksum_type: str = 'sha256') -> bool:
        """
        Verify file checksum

        Args:
            file_path: Path to file
            expected_checksum: Expected checksum value
            checksum_type: Type of checksum ('md5', 'sha1', 'sha256', 'crc32')

        Returns:
            True if checksum matches
        """
        import hashlib

        try:
            if checksum_type.lower() == 'crc32':
                crc = 0
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        crc = zlib.crc32(chunk, crc)
                calculated = format(crc & 0xFFFFFFFF, '08X')
            else:
                hasher = hashlib.new(checksum_type.lower())
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)
                calculated = hasher.hexdigest()

            return calculated.lower() == expected_checksum.lower()

        except Exception:
            return False

    @staticmethod
    def calculate_checksum(file_path: Path, checksum_type: str = 'sha256') -> Optional[str]:
        """
        Calculate file checksum

        Args:
            file_path: Path to file
            checksum_type: Type of checksum ('md5', 'sha1', 'sha256', 'crc32')

        Returns:
            Checksum string or None on error
        """
        import hashlib

        try:
            if checksum_type.lower() == 'crc32':
                crc = 0
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        crc = zlib.crc32(chunk, crc)
                return format(crc & 0xFFFFFFFF, '08X')
            else:
                hasher = hashlib.new(checksum_type.lower())
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)
                return hasher.hexdigest()

        except Exception:
            return None
