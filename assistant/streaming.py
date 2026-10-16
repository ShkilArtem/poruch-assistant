import re


def speech_parts(buffer, *, final=False, first=False):
    """Emit complete sentences or bounded phrases, retaining an unfinished tail."""
    parts = []
    while buffer:
        boundary = re.search(r'[.!?…][»”"\)\]]*(?=\s)', buffer)
        words = list(re.finditer(r'\S+\s+', buffer))
        if first and len(words) >= 4 and (not boundary or boundary.end() > words[3].end()):
            end = words[3].end()
        elif boundary and boundary.end() <= 180:
            end = boundary.end()
        elif first and len(buffer) >= 48 and words:
            end = next((word.end() for word in words if word.end() >= 32), words[-1].end())
        elif len(buffer) >= 180:
            end = buffer.rfind(' ', 0, 160)
            if end < 1:
                end = 160
        elif final:
            end = len(buffer)
        else:
            break
        part, buffer = buffer[:end].strip(), buffer[end:].lstrip()
        if part:
            parts.append(part)
            first = False
    return parts, buffer
