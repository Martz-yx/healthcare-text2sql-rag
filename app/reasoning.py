import re


class ReasoningFilter:
    """Filters <think>...</think> blocks and [Routing] headers from streamed LLM output."""

    def __init__(self, strip_think: bool = True):
        self._in_think = False
        self._buffer = ""
        self.strip_think = strip_think

    def process(self, chunk: str) -> str:
        result = []
        self._buffer += chunk

        while self._buffer:
            if self._in_think:
                end = self._buffer.find("</think>")
                if end == -1:
                    # Not found yet, but check if we are accumulating too much or wait for tag
                    if not self.strip_think:
                        # If we want to show thinking, stream everything up to the last 10 chars (in case they form "</think>")
                        if len(self._buffer) > 10:
                            safe = self._buffer[:-10]
                            self._buffer = self._buffer[-10:]
                            # add blockquote prefix to newlines if we want it formatted as blockquote
                            safe = safe.replace("\n", "\n> ")
                            result.append(safe)
                    else:
                        if len(self._buffer) > 5000:
                            self._in_think = False
                            self._buffer = ""
                    return "".join(result)
                
                # Found </think>
                if not self.strip_think:
                    safe = self._buffer[:end].replace("\n", "\n> ")
                    result.append(safe + "\n\n")
                
                self._buffer = self._buffer[end + len("</think>"):]
                self._in_think = False
                continue

            start = self._buffer.find("<think>")
            if start != -1:
                result.append(self._buffer[:start])
                if not self.strip_think:
                    result.append("\n\n> **Razonamiento:**\n> ")
                
                self._buffer = self._buffer[start + len("<think>"):]
                self._in_think = True
                continue


            if "<think" in self._buffer[-10:]:
                safe = self._buffer[:-10]
                self._buffer = self._buffer[-10:]
                if safe:
                    result.append(safe)
                break

            result.append(self._buffer)
            self._buffer = ""

        text = "".join(result)
        text = re.sub(
            r"\[Routing\].*?(?:Model Used:.*?\n|$)",
            "", text, flags=re.DOTALL,
        )
        return text

    def flush(self) -> str:
        if self._in_think and not self.strip_think:
            remaining = self._buffer.replace("\n", "\n> ")
            self._buffer = ""
            self._in_think = False
            return remaining

        remaining = self._buffer
        self._buffer = ""
        return remaining
