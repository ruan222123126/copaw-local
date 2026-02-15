# -*- coding: utf-8 -*-
import os
import base64
import hashlib
import logging
import shutil
import subprocess
import urllib.parse
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Global token counter instance (lazy initialization)
_token_counter = None


async def download_file_from_base64(
    base64_data: str,
    filename: Optional[str] = None,
    download_dir: str = "downloads",
) -> str:
    """
    Save base64-encoded file data to local download directory.

    Args:
        base64_data (`str`):
            Base64-encoded file content.
        filename (`str`, optional):
            The filename to save. If not provided, will generate one.
        download_dir (`str`):
            The directory to save files. Defaults to "downloads".

    Returns:
        `str`:
            The local file path.
    """
    try:
        # Decode base64 data
        file_content = base64.b64decode(base64_data)

        # Create download directory if not exists
        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)

        # Generate filename if not provided
        if not filename:
            # Use hash of content as filename
            file_hash = hashlib.md5(file_content).hexdigest()
            filename = f"file_{file_hash}"

        # Save file
        local_file_path = download_path / filename
        with open(local_file_path, "wb") as f:
            f.write(file_content)

        logger.debug("Downloaded file to: %s", local_file_path)
        return str(local_file_path.absolute())

    except Exception as e:
        logger.error("Failed to download file from base64: %s", e)
        raise


async def download_file_from_url(
    url: str,
    filename: Optional[str] = None,
    download_dir: str = "downloads",
) -> str:
    """
    Download a file from URL to local download directory using wget or curl.

    Args:
        url (`str`):
            The URL of the file to download.
        filename (`str`, optional):
            The filename to save. If not provided, will extract from URL or
            generate a hash-based name.
        download_dir (`str`):
            The directory to save files. Defaults to "downloads".

    Returns:
        `str`:
            The local file path.
    """
    try:
        # Create download directory if not exists
        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)

        # Generate filename if not provided
        if not filename:
            # Try to extract filename from URL
            parsed_url = urllib.parse.urlparse(url)
            url_filename = os.path.basename(parsed_url.path)
            if url_filename:
                filename = url_filename
            else:
                # Use hash of URL as filename
                url_hash = hashlib.md5(url.encode()).hexdigest()
                filename = f"file_{url_hash}"

        # Full local file path
        local_file_path = download_path / filename

        # Try wget first, then curl, then fall back to urllib (for Windows)
        download_success = False
        try:
            subprocess.run(
                ["wget", "-q", "-O", str(local_file_path), url],
                capture_output=True,
                timeout=60,
                check=True,
            )
            logger.debug("Downloaded file via wget to: %s", local_file_path)
            download_success = True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # wget failed or not available, try curl
            logger.debug("wget failed, trying curl: %s", e)
            try:
                subprocess.run(
                    ["curl", "-s", "-L", "-o", str(local_file_path), url],
                    capture_output=True,
                    timeout=60,
                    check=True,
                )
                logger.debug(
                    "Downloaded file via curl to: %s",
                    local_file_path,
                )
                download_success = True
            except (
                subprocess.CalledProcessError,
                FileNotFoundError,
            ) as curl_err:
                # curl also failed, fall back to urllib
                logger.debug("curl failed, trying urllib: %s", curl_err)
                try:
                    import urllib.request as _urlreq

                    _urlreq.urlretrieve(url, str(local_file_path))
                    logger.debug(
                        "Downloaded file via urllib to: %s",
                        local_file_path,
                    )
                    download_success = True
                except Exception as urllib_err:
                    logger.error(
                        "wget, curl and urllib all failed for URL %s: %s",
                        url,
                        urllib_err,
                    )
                    raise RuntimeError(
                        "Failed to download file: "
                        "wget, curl and urllib all failed",
                    ) from urllib_err

        # Verify file was downloaded
        if not download_success or not local_file_path.exists():
            raise FileNotFoundError("Downloaded file does not exist")

        if local_file_path.stat().st_size == 0:
            raise ValueError("Downloaded file is empty")

        return str(local_file_path.absolute())

    except subprocess.TimeoutExpired as e:
        logger.error("Download timeout for URL: %s", url)
        raise TimeoutError(f"Download timeout for URL: {url}") from e
    except Exception as e:
        logger.error("Failed to download file from URL %s: %s", url, e)
        raise


async def _process_single_file_block(
    source: dict,
    filename: Optional[str],
) -> Optional[str]:
    """
    Process a single file block and download the file.

    Args:
        source (`dict`):
            The source dict containing file information.
        filename (`str`, optional):
            The filename to save.

    Returns:
        `str` or `None`:
            The local file path if successful, None otherwise.
    """
    # Handle Base64Source
    if isinstance(source, dict) and source.get("type") == "base64":
        # Check if 'data' key exists (allow empty string)
        if "data" in source:
            base64_data = source.get("data", "")
            local_path = await download_file_from_base64(
                base64_data,
                filename,
            )
            logger.debug(
                "Processed base64 file block: %s -> %s",
                filename or "unnamed",
                local_path,
            )
            return local_path

    # Handle URLSource
    elif isinstance(source, dict) and source.get("type") == "url":
        # Check if 'url' key exists and is not empty
        url = source.get("url", "")
        if url:
            local_path = await download_file_from_url(
                url,
                filename,
            )
            logger.debug(
                "Processed URL file block: %s -> %s",
                url,
                local_path,
            )
            return local_path

    return None


def _extract_source_and_filename(block: dict, block_type: str):
    """Extract source and filename from a block."""
    if block_type == "file":
        return block.get("source", {}), block.get("filename")

    # Media blocks (image, audio, video)
    source = block.get("source", {})
    if not isinstance(source, dict):
        return None, None

    # Try to extract filename from URL
    filename = None
    if source.get("type") == "url":
        url = source.get("url", "")
        if url:
            parsed = urllib.parse.urlparse(url)
            filename = os.path.basename(parsed.path) or None

    return source, filename


def _update_block_with_local_path(
    block: dict,
    block_type: str,
    local_path: str,
) -> dict:
    """Update block with downloaded local path."""
    if block_type == "file":
        # File block: update source directly
        block["source"] = local_path
        if not block.get("filename"):
            block["filename"] = os.path.basename(local_path)
    else:
        # Media blocks: update source with URL structure
        block["source"] = {"type": "url", "url": Path(local_path).as_uri()}
    return block


def _handle_download_failure(block_type: str) -> Optional[dict]:
    """Handle download failure based on block type."""
    if block_type == "file":
        # File block: return error text block
        return {
            "type": "text",
            "text": "[Error: Unknown file source type or empty data]",
        }
    # Media blocks: return None to keep original
    logger.debug("Failed to download %s block, keeping original", block_type)
    return None


async def _process_single_block(
    message_content: list,
    index: int,
    block: dict,
) -> Optional[str]:
    """
    Process a single file or media block.

    Returns:
        Optional[str]: The local path if download was successful,
        None otherwise.
    """
    block_type = block.get("type")
    if not isinstance(block_type, str):
        return None

    # Extract source and filename
    source, filename = _extract_source_and_filename(block, block_type)
    if source is None:
        return None

    try:
        # Download to local
        local_path = await _process_single_file_block(source, filename)

        if local_path:
            # Update block with local path
            message_content[index] = _update_block_with_local_path(
                block,
                block_type,
                local_path,
            )
            logger.debug(
                "Updated %s block with local path: %s",
                block_type,
                local_path,
            )
            return local_path
        else:
            # Handle download failure
            error_block = _handle_download_failure(block_type)
            if error_block:
                message_content[index] = error_block
            return None

    except Exception as e:
        logger.error("Failed to process %s block: %s", block_type, e)
        # File block: replace with error; Media blocks: keep original
        if block_type == "file":
            message_content[index] = {
                "type": "text",
                "text": f"[Error: Failed to download file - {e}]",
            }
        return None


async def process_file_and_media_blocks_in_message(msg) -> None:
    """
    Process file and media blocks (file, image, audio, video) in messages.
    Downloads to local and updates paths/URLs.

    Args:
        msg: The message object (Msg or list[Msg]) to process.
    """
    from agentscope.message import Msg

    messages = (
        [msg] if isinstance(msg, Msg) else msg if isinstance(msg, list) else []
    )

    for message in messages:
        if not isinstance(message, Msg):
            continue

        if not isinstance(message.content, list):
            continue

        # Collect download results with their indices
        downloaded_files = []

        # Process each content block
        for i, block in enumerate(message.content):
            if not isinstance(block, dict):
                continue

            block_type = block.get("type")
            if block_type not in ["file", "image", "audio", "video"]:
                continue

            local_path = await _process_single_block(message.content, i, block)
            if local_path:
                downloaded_files.append((i, local_path))

        # Add text blocks for successfully downloaded files
        for i, local_path in reversed(downloaded_files):
            text_block = {
                "type": "text",
                "text": f"用户上传文件，已经下载到 {local_path}",
            }
            # Insert the text block right after the file block
            message.content.insert(i + 1, text_block)


def copy_md_files(language: str) -> int:
    """Copy md files from agents/md_files to working directory.

    Args:
        language: Language code (e.g. 'en', 'zh')

    Returns:
        Number of md files copied
    """
    from ..constant import WORKING_DIR

    # Get md_files directory path with language subdirectory
    md_files_dir = Path(__file__).parent / "md_files" / language

    if not md_files_dir.exists():
        logger.warning(
            "MD files directory not found: %s, falling back to 'en'",
            md_files_dir,
        )
        # Fallback to English if specified language not found
        md_files_dir = Path(__file__).parent / "md_files" / "en"
        if not md_files_dir.exists():
            logger.error("Default 'en' md files not found either")
            return 0

    # Ensure working directory exists
    WORKING_DIR.mkdir(parents=True, exist_ok=True)

    # Copy all .md files to working directory
    copied_count = 0
    for md_file in md_files_dir.glob("*.md"):
        target_file = WORKING_DIR / md_file.name
        try:
            shutil.copy2(md_file, target_file)
            logger.debug("Copied md file: %s", md_file.name)
            copied_count += 1
        except Exception as e:
            logger.error(
                "Failed to copy md file '%s': %s",
                md_file.name,
                e,
            )

    if copied_count > 0:
        logger.debug(
            "Copied %d md file(s) [%s] to %s",
            copied_count,
            language,
            WORKING_DIR,
        )

    return copied_count


def _get_token_counter():
    """Get or initialize the global token counter instance.

    Returns:
        TokenCounterBase: The token counter instance for Qwen models.

    Raises:
        RuntimeError: If token counter initialization fails.
    """
    global _token_counter
    if _token_counter is None:
        from agentscope.token import HuggingFaceTokenCounter

        # Use Qwen tokenizer for DashScope models
        # Qwen3 series uses the same tokenizer as Qwen2.5

        # Try local tokenizer first, fall back to online if not found
        local_tokenizer_path = Path(__file__).parent.parent / "tokenizer"

        if (
            local_tokenizer_path.exists()
            and (local_tokenizer_path / "tokenizer.json").exists()
        ):
            tokenizer_path = str(local_tokenizer_path)
            logger.info(f"Using local Qwen tokenizer from {tokenizer_path}")
        else:
            tokenizer_path = "Qwen/Qwen2.5-7B-Instruct"
            logger.info(
                "Local tokenizer not found, downloading from HuggingFace",
            )

        _token_counter = HuggingFaceTokenCounter(
            pretrained_model_name_or_path=tokenizer_path,
            use_mirror=True,  # Use HF mirror for users in China
            use_fast=True,
            trust_remote_code=True,
        )
        logger.debug("Token counter initialized with Qwen tokenizer")
    return _token_counter


def _extract_text_from_messages(messages: list[dict]) -> str:
    """Extract text content from messages and concatenate into a string.

    Handles various message formats:
    - Simple string content: {"role": "user", "content": "hello"}
    - List content with text blocks:
      {"role": "user", "content": [{"type": "text", "text": "hello"}]}

    Args:
        messages: List of message dictionaries in chat format.

    Returns:
        str: Concatenated text content from all messages.
    """
    parts = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    # Support {"type": "text", "text": "..."} format
                    text = block.get("text") or block.get("content", "")
                    if text:
                        parts.append(str(text))
                elif isinstance(block, str):
                    parts.append(block)
    return "\n".join(parts)


async def count_message_tokens(
    messages: list[dict],
) -> int:
    """Count tokens in messages using the tokenizer.

    Extracts text content from messages and uses the tokenizer to
    count tokens. This approach is more robust across different model
    types than using apply_chat_template directly.

    Args:
        messages: List of message dictionaries in chat format.

    Returns:
        int: The estimated number of tokens in the messages.

    Raises:
        RuntimeError: If token counter fails to initialize.
    """
    token_counter = _get_token_counter()
    text = _extract_text_from_messages(messages)
    token_ids = token_counter.tokenizer.encode(text)
    token_count = len(token_ids)
    logger.debug(
        "Counted %d tokens in %d messages",
        token_count,
        len(messages),
    )
    return token_count


def check_valid_messages(messages: list) -> bool:
    """
    Check if the messages are valid by ensuring all tool_use blocks have
    corresponding tool_result blocks.

    Args:
        messages: List of Msg objects to validate.

    Returns:
        bool: True if all tool_use IDs have matching tool_result IDs,
              False otherwise.
    """

    def _get_tool_ids(msgs: list, block_type: str) -> set[str]:
        """Get all block ids of specified type from messages."""
        ids = set()
        for msg in msgs:
            if not isinstance(msg.content, list):
                continue
            for block in msg.content:
                if isinstance(block, dict) and block.get("type") == block_type:
                    block_id = block.get("id")
                    if block_id:
                        ids.add(block_id)
        return ids

    tool_use_ids = _get_tool_ids(messages, "tool_use")
    tool_result_ids = _get_tool_ids(messages, "tool_result")
    return tool_use_ids == tool_result_ids


def is_first_user_interaction(messages: list) -> bool:
    """Check if this is the first user interaction.

    Args:
        messages: List of Msg objects from memory.

    Returns:
        bool: True if this is the first user message with no assistant
              responses.
    """
    system_prompt_count = sum(1 for msg in messages if msg.role == "system")
    non_system_messages = messages[system_prompt_count:]

    user_msg_count = sum(
        1 for msg in non_system_messages if msg.role == "user"
    )
    assistant_msg_count = sum(
        1 for msg in non_system_messages if msg.role == "assistant"
    )

    return user_msg_count == 1 and assistant_msg_count == 0


def prepend_to_message_content(msg, guidance: str) -> None:
    """Prepend guidance text to message content.

    Args:
        msg: Msg object to modify.
        guidance: Text to prepend to the message content.
    """
    if isinstance(msg.content, str):
        msg.content = guidance + "\n\n" + msg.content
        return

    if not isinstance(msg.content, list):
        return

    for block in msg.content:
        if isinstance(block, dict) and block.get("type") == "text":
            block["text"] = guidance + "\n\n" + block.get("text", "")
            return

    msg.content.insert(0, {"type": "text", "text": guidance})
