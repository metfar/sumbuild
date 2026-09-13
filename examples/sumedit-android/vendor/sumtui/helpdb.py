#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018- William Martinez Bas <metfar@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#
"""Read-only help data consumed by sumTUI help viewers.

The canonical Markdown ↔ ``.helpdb`` parser/serializer is owned by SumDoc.
sumTUI keeps only the small runtime model needed to load a compiled helpdb and
render topics. Legacy conversion methods delegate lazily to SumDoc when it is
installed, so existing callers have a migration path without making SumDoc a
runtime dependency of the TUI toolkit.
""";

from dataclasses import dataclass;
import json;
from pathlib import Path;


@dataclass(frozen=True)
class HelpTopic:
    name: str;
    category: str;
    summary: str;
    syntax: tuple;
    example: str;
    notes: tuple = tuple();
    see_also: tuple = tuple();
    aliases: tuple = tuple();
    language: str = "text";

    def markdown(self):
        lines = ["# {}".format(self.name), "", self.summary, "", "## Syntax", "", "```{}".format(self.language)];
        lines.extend(self.syntax);
        lines.append("```");
        if self.notes:
            lines.extend(["", "## Notes", ""]);
            lines.extend(["- {}".format(item) for item in self.notes]);
        lines.extend(["", "## Functional example", "", "```{}".format(self.language)]);
        lines.extend(self.example.rstrip().splitlines());
        lines.append("```");
        if self.see_also:
            lines.extend(["", "## See also", "", ", ".join(self.see_also)]);
        if self.aliases:
            lines.extend(["", "## Aliases", "", ", ".join(self.aliases)]);
        return "\n".join(lines).rstrip();


class HelpCorpus:
    def __init__(self, title, topics=None, intro=""):
        self.title = str(title or "Help");
        self.intro = str(intro or "").strip();
        self.topics = tuple(topics or ());
        self._topic_map = {topic.name.upper(): topic for topic in self.topics};
        self._aliases = {};
        for topic in self.topics:
            for alias in topic.aliases:
                self._aliases[str(alias).strip().upper()] = topic.name.upper();

    def topic_names(self):
        return [topic.name for topic in sorted(self.topics, key=lambda item: (item.category.casefold(), item.name.casefold()))];

    def find_topic(self, name):
        raw = str(name or "").strip().upper();
        raw = self._aliases.get(raw, raw);
        if raw in self._topic_map:
            return self._topic_map[raw];
        matches = [topic for key, topic in self._topic_map.items() if key.startswith(raw)] if raw else [];
        return matches[0] if len(matches) == 1 else None;

    def index_markdown(self):
        lines = ["# {}".format(self.title), ""];
        if self.intro:
            lines.extend([self.intro, ""]);
        categories = {};
        for topic in sorted(self.topics, key=lambda item: (item.category.casefold(), item.name.casefold())):
            categories.setdefault(topic.category, []).append(topic);
        for category, topics in categories.items():
            lines.extend(["## {}".format(category), ""]);
            for topic in topics:
                lines.append("- **{}** — {}".format(topic.name, topic.summary));
            lines.append("");
        return "\n".join(lines).rstrip();

    def to_dict(self):
        return {
            "schema_version": 1,
            "title": self.title,
            "intro": self.intro,
            "topics": [
                {
                    "name": topic.name,
                    "category": topic.category,
                    "summary": topic.summary,
                    "syntax": list(topic.syntax),
                    "example": topic.example,
                    "notes": list(topic.notes),
                    "see_also": list(topic.see_also),
                    "aliases": list(topic.aliases),
                    "language": topic.language,
                }
                for topic in self.topics
            ],
        };

    @classmethod
    def from_dict(cls, data):
        if int(data.get("schema_version", 0)) != 1:
            raise ValueError("unsupported helpdb schema version");
        topics = [];
        for item in data.get("topics", []):
            topics.append(HelpTopic(
                str(item.get("name", "")),
                str(item.get("category", "General")),
                str(item.get("summary", "")),
                tuple(str(value) for value in item.get("syntax", [])),
                str(item.get("example", "")),
                tuple(str(value) for value in item.get("notes", [])),
                tuple(str(value) for value in item.get("see_also", [])),
                tuple(str(value) for value in item.get("aliases", [])),
                str(item.get("language", "text")),
            ));
        return cls(data.get("title", "Help"), topics, intro=data.get("intro", ""));

    @classmethod
    def from_helpdb(cls, text):
        return cls.from_dict(json.loads(str(text)));

    @classmethod
    def from_markdown(cls, text):
        """Compatibility bridge; new conversion code belongs to ``sumdoc``.""";
        try:
            from sumdoc.helpdb import HelpCorpus as SumDocHelpCorpus;
        except ImportError as error:
            raise RuntimeError("Markdown help parsing moved to sumdoc>=0.2.1; install SumDoc for conversion workflows.") from error;
        return cls.from_dict(SumDocHelpCorpus.from_markdown(text).to_dict());

    def to_helpdb(self, indent=2):
        """Compatibility bridge; new conversion code belongs to ``sumdoc``.""";
        try:
            from sumdoc.helpdb import HelpCorpus as SumDocHelpCorpus;
        except ImportError as error:
            raise RuntimeError("helpdb serialization moved to sumdoc>=0.2.1; install SumDoc for conversion workflows.") from error;
        return SumDocHelpCorpus.from_dict(self.to_dict()).to_helpdb(indent=indent);

    def to_markdown(self):
        """Compatibility bridge for corpus serialization; topic rendering stays local.""";
        try:
            from sumdoc.helpdb import HelpCorpus as SumDocHelpCorpus;
        except ImportError as error:
            raise RuntimeError("help Markdown serialization moved to sumdoc>=0.2.1; install SumDoc for conversion workflows.") from error;
        return SumDocHelpCorpus.from_dict(self.to_dict()).to_markdown();


def load_helpdb(path):
    return HelpCorpus.from_helpdb(Path(path).read_text(encoding="utf-8"));
