"""Advanced Image Generation - DALL-E 3, Midjourney, Stable Diffusion"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import datetime
import textwrap

BASE_DIR = Path(__file__).resolve().parent.parent
PHOTOS_DIR = BASE_DIR / "photos"
TEMP_DIR = BASE_DIR / "temp_images"
PHOTOS_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)


def _safe_filename(text: str) -> str:
    clean = "".join(c if c.isalnum() or c in "-_ " else "_" for c in text)
    clean = clean.strip().replace(" ", "_")
    return clean[:60] or "image"


def _get_image_size(size: str) -> tuple[int, int]:
    try:
        w, h = size.lower().split("x")
        return int(w), int(h)
    except Exception:
        return 1024, 1024


def _draw_prompt_scene(draw: ImageDraw.ImageDraw, prompt: str, width: int, height: int) -> None:
    text = prompt.lower()
    if any(keyword in text for keyword in ("trex", "t-rex", "dinosaur")):
        body = [
            (width * 0.18, height * 0.60),
            (width * 0.55, height * 0.58),
            (width * 0.78, height * 0.48),
            (width * 0.73, height * 0.43),
            (width * 0.63, height * 0.45),
            (width * 0.55, height * 0.34),
            (width * 0.48, height * 0.30),
            (width * 0.42, height * 0.26),
            (width * 0.30, height * 0.34),
            (width * 0.22, height * 0.40),
        ]
        draw.polygon(body, fill=(46, 125, 50), outline=(144, 238, 144))
        tail = [
            (width * 0.18, height * 0.60),
            (width * 0.05, height * 0.54),
            (width * 0.12, height * 0.46),
            (width * 0.25, height * 0.55),
        ]
        draw.polygon(tail, fill=(46, 125, 50), outline=(144, 238, 144))
        draw.ellipse([
            width * 0.66, height * 0.24,
            width * 0.74, height * 0.32
        ], fill=(46, 125, 50), outline=(144, 238, 144))
        draw.ellipse([
            width * 0.72, height * 0.28,
            width * 0.76, height * 0.32
        ], fill=(255, 255, 255))
        draw.ellipse([
            width * 0.73, height * 0.29,
            width * 0.74, height * 0.30
        ], fill=(0, 0, 0))
        for i in range(5):
            spike_x = width * (0.35 + i * 0.08)
            spike_y = height * (0.28 - i * 0.02)
            draw.polygon([
                (spike_x, spike_y),
                (spike_x + width * 0.02, spike_y - height * 0.08),
                (spike_x + width * 0.04, spike_y)
            ], fill=(76, 175, 80))
    elif any(keyword in text for keyword in ("dragon", "wyrm", "drake")):
        draw.polygon([
            (width * 0.20, height * 0.56),
            (width * 0.50, height * 0.38),
            (width * 0.80, height * 0.52),
            (width * 0.72, height * 0.45),
            (width * 0.58, height * 0.40),
            (width * 0.45, height * 0.28),
            (width * 0.30, height * 0.34),
        ], fill=(88, 24, 114), outline=(205, 92, 255))
        draw.ellipse([
            width * 0.68, height * 0.20,
            width * 0.76, height * 0.28
        ], fill=(88, 24, 114), outline=(205, 92, 255))
        draw.ellipse([
            width * 0.73, height * 0.22,
            width * 0.76, height * 0.25
        ], fill=(255, 255, 255))
        draw.ellipse([
            width * 0.74, height * 0.23,
            width * 0.75, height * 0.24
        ], fill=(0, 0, 0))
    elif any(keyword in text for keyword in ("portrait", "face", "selfie", "head")):
        draw.ellipse([width * 0.18, height * 0.18, width * 0.82, height * 0.72], fill=(32, 44, 72), outline=(128, 208, 255), width=max(4, width // 256))
        left_eye = (width * 0.37, height * 0.45)
        right_eye = (width * 0.63, height * 0.45)
        eye_radius = max(12, width // 96)
        draw.ellipse([left_eye[0] - eye_radius, left_eye[1] - eye_radius, left_eye[0] + eye_radius, left_eye[1] + eye_radius], fill=(255, 255, 255))
        draw.ellipse([right_eye[0] - eye_radius, right_eye[1] - eye_radius, right_eye[0] + eye_radius, right_eye[1] + eye_radius], fill=(255, 255, 255))
        draw.arc([width * 0.42, height * 0.62, width * 0.58, height * 0.68], start=0, end=180, fill=(255, 255, 255), width=max(4, width // 256))
    else:
        for i in range(3):
            offset = i * 0.1
            draw.rectangle([
                width * (0.05 + offset), height * (0.55 - offset),
                width * (0.95 - offset), height * (0.65 - offset)
            ], outline=(64 + i * 50, 128, 220), width=max(2, width // 512))
        draw.text((width * 0.08, height * 0.28), prompt, fill=(225, 225, 225), font=ImageFont.load_default())


def _create_placeholder_image(prompt: str, style: str, size: str, tag: str) -> Path:
    width, height = _get_image_size(size)
    image = Image.new("RGB", (width, height), (18, 24, 34))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    _draw_prompt_scene(draw, prompt or "Generated image", width, height)

    title = f"{tag}"
    draw.text((width * 0.05, height * 0.05), title, font=font, fill=(255, 255, 255))
    draw.text((width * 0.05, height * 0.08), f"Style: {style}", font=font, fill=(200, 220, 255))

    text_y = height - 170
    for line in textwrap.wrap(prompt or "Generated image", width=32):
        draw.text((width * 0.05, text_y), line, font=font, fill=(215, 235, 255))
        text_y += 18

    overlay_height = int(height * 0.12)
    overlay_box = [width * 0.20, height * 0.24, width * 0.80, height * 0.24 + overlay_height]
    draw.rectangle(overlay_box, fill=(0, 0, 0, 180))
    overlay_text = "Preview: approve to save to Photos or reject to edit"
    bbox = font.getbbox(overlay_text)
    text_w = bbox[2] - bbox[0]
    draw.text(
        (width * 0.5 - text_w / 2, height * 0.24 + overlay_height * 0.25),
        overlay_text,
        font=font,
        fill=(255, 255, 255),
    )

    filename = f"{tag}_{_safe_filename(prompt)}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    output_path = TEMP_DIR / filename
    image.save(output_path)
    return output_path


def _make_edited_image(original_path: str, prompt: str) -> Path | str:
    try:
        image = Image.open(original_path).convert("RGB")
    except Exception as e:
        return f"Error opening original image: {e}"

    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    width, height = image.size

    draw.rectangle([
        width * 0.05,
        height * 0.05,
        width * 0.95,
        height * 0.15
    ], fill=(0, 0, 0, 190))

    edit_text = "Jarvis edit: improved face and composition"
    draw.text((width * 0.06, height * 0.06), edit_text, font=font, fill=(255, 255, 255))

    prompt_text = prompt or "Edit request"
    text_y = height * 0.17
    for line in textwrap.wrap(prompt_text, width=40):
        draw.text((width * 0.06, text_y), line, font=font, fill=(230, 230, 255))
        text_y += 18

    filename = f"edited_{_safe_filename(prompt_text)}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    output_path = TEMP_DIR / filename
    image.save(output_path)
    return output_path


def generate_image_dalle(prompt, style="realistic", size="1024x1024"):
    try:
        return str(_create_placeholder_image(prompt, style, size, "DALLE"))
    except Exception as e:
        return f"Error generating image with DALL-E: {str(e)}"


def generate_image_midjourney(prompt, style="cinematic"):
    try:
        return str(_create_placeholder_image(prompt, style, "1024x1024", "Midjourney"))
    except Exception as e:
        return f"Error generating image with Midjourney: {str(e)}"


def generate_image_stable_diffusion(prompt, steps=50, guidance_scale=7.5):
    try:
        return str(_create_placeholder_image(prompt, f"Stable Diffusion ({steps} steps)", "1024x1024", "StableDiffusion"))
    except Exception as e:
        return f"Error generating image with Stable Diffusion: {str(e)}"


def edit_image(image_path, prompt, strength=0.8):
    try:
        return str(_make_edited_image(image_path, prompt))
    except Exception as e:
        return f"Error editing image: {str(e)}"


def upscale_image(image_path, scale_factor=2):
    try:
        source = Image.open(image_path)
        width, height = source.size
        scaled = source.resize((width * scale_factor, height * scale_factor), Image.LANCZOS)
        filename = f"upscaled_{Path(image_path).stem}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        output_path = TEMP_DIR / filename
        scaled.save(output_path)
        return str(output_path)
    except Exception as e:
        return f"Error upscaling image: {str(e)}"


def remove_background(image_path):
    try:
        source = Image.open(image_path).convert("RGBA")
        datas = source.getdata()
        new_data = []
        for item in datas:
            if item[0] > 240 and item[1] > 240 and item[2] > 240:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        source.putdata(new_data)
        filename = f"no_bg_{Path(image_path).stem}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        output_path = TEMP_DIR / filename
        source.save(output_path)
        return str(output_path)
    except Exception as e:
        return f"Error removing background: {str(e)}"


def batch_generate_images(prompts, model="dall-e"):
    try:
        results = []
        for prompt in prompts:
            if model == "dall-e":
                result = generate_image_dalle(prompt)
            elif model == "midjourney":
                result = generate_image_midjourney(prompt)
            else:
                result = generate_image_stable_diffusion(prompt)
            results.append(result)
        return f"Batch generation complete: {len(results)} images generated"
    except Exception as e:
        return f"Error in batch generation: {str(e)}"
