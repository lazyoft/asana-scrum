import re


class NameParser:
    __name_regex = re.compile("(?P<name>[^(]+)([(](?P<abbr>[^)]+))?")
    __clean_regex = re.compile("\\[[^]]*\\]*")

    def __init__(self, name: str):
        self.raw = name

    # Returns the name without the tags
    @property
    def untagged(self) -> str:
        return self.__clean_regex.sub("", self.raw).strip()

    # Returns the parts making up a name separated with ">"
    @property
    def parts(self) -> list:
        return [part.strip() for part in self.untagged.split(">")]

    # Returns the first part of a name separated with ">"
    @property
    def first(self) -> str:
        return self.parts[0]

    # Returns the remainder of a name separated with ">" after the first part is stripped
    @property
    def remainder(self) -> str:
        return " > ".join(self.parts[1:])

    # Returns the actual name without the mnemonic
    @property
    def name(self) -> str:
        return self.__name_regex.match(self.first).group("name").strip()

    # Returns the actual short name if present
    @property
    def abbreviation(self) -> str:
        result = self.__name_regex.match(self.first).group("abbr")
        return result.strip() if result is not None else None

    # Returns the mnemonic of the name aka the name within parenthesis if present or the name itself
    @property
    def mnemonic(self) -> str:
        return self.abbreviation or self.name

    def matches(self, name: str) -> bool:
        name_name = self.__name_regex.match(name).group("name").strip()
        name_abbreviation = self.__name_regex.match(name).group("abbr")
        name_mnemonic = name_abbreviation or name_name

        return len(self.parts) == 1 and (name_mnemonic == self.mnemonic or name_name == self.name)
