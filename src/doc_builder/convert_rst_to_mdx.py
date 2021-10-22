import re


# Re pattern to catch things inside ` ` in :obj:`thing`.
_re_obj = re.compile(r":obj:`([^`]+)`")
# Re pattern to catch things inside ` ` in :math:`thing`.
_re_math = re.compile(r":math:`([^`]+)`")
# Re pattern to catch things between single backquotes.
_re_single_backquotes = re.compile(r"(^|[^`])`([^`]+)`([^`]|$)")
# Re pattern to catch things between double backquotes.
_re_double_backquotes = re.compile(r"(^|[^`])``([^`]+)``([^`]|$)")
# Re pattern to catch things inside ` ` in :func/class/meth:`thing`.
_re_func_class = re.compile(r":(?:func|class|meth):`([^`]+)`")


def convert_rst_formatting(text):
    """
    Convert rst syntax for formatting to markdown in a given text.
    """
    # Remove :class:, :func: and :meth: markers. To code-links and put double backquotes
    # (to not be caught by the italic conversion).
    text = _re_func_class.sub(r"[``\1``]", text)
    # Remove :obj: markers. What's after is in a single backquotes so we put in double backquotes 
    # (to not be caught by the italic conversion).
    text = _re_obj.sub(r"``\1``", text)
    # Remove :math: markers.
    text = _re_math.sub(r"\\\\(\1\\\\)", text)
    # Convert content in single backquotes to italic.
    text = _re_single_backquotes.sub(r'\1_\2_\3', text)
    # Convert content in double backquotes to single backquotes.
    text = _re_double_backquotes.sub(r'\1`\2`\3', text)
    # Remove remaining ::
    text = re.sub(r"::\n", "", text)
    
    # Remove new lines inside blocks in backsticks as they will be kept.
    lines = text.split("\n")
    in_code = False
    text = None
    for line in lines:
        if in_code:
            splits = line.split("`")
            in_code = (len(splits) > 1 and len(splits) % 2 == 1)
            if len(splits) == 1:
                # Some forgotten lone backstick
                text += "\n" + line
            else:
                text += " " + line.lstrip()
        else:
            if text is not None:
                text += "\n" + line
            else:
                text = line
            splits = line.split("`")
            in_code = (len(splits) % 2 == 0)
    return text


# Re pattern to catch description and url in links of the form `description <url>`_.
_re_links = re.compile(r"`([^`]+\S)\s+</*([^/][^>`]*)>`_+")
# Re pattern to catch description and url in links of the form :prefix_link:`description <url>`_.
_re_prefix_links = re.compile(r":prefix_link:`([^`]+\S)\s+</*([^/][^>`]*)>`")
# Re pattern to catch reference in links of the form :doc:`reference`.
_re_simple_doc = re.compile(r":doc:`([^`<]*)`")
# Re pattern to catch description and reference in links of the form :doc:`description <reference>`.
_re_doc_with_description = re.compile(r":doc:`([^`<]+\S)\s+</*([^/][^>`]*)>`")
# Re pattern to catch reference in links of the form :ref:`reference`.
_re_simple_ref = re.compile(r":ref:`([^`<]*)`")
# Re pattern to catch description and reference in links of the form :ref:`description <reference>`.
_re_ref_with_description = re.compile(r":ref:`([^`<]+\S)\s+<([^>]*)>`")


def convert_rst_links(text, page_info):
    """
    Convert the rst links in text to markdown.
    """
    if "package_name" not in page_info:
        raise ValueError("`page_info` must contain at least the package_name.")
    package_name = page_info["package_name"]
    version = page_info.get("version", "master")
    language = page_info.get("language", "en")

    prefix = f"/docs/{package_name}/{version}/{language}/"
    # Links of the form :doc:`page`
    text = _re_simple_doc.sub(rf'[\1]({prefix}\1.html)', text)
    # Links of the form :doc:`text <page>`
    text = _re_doc_with_description.sub(rf'[\1]({prefix}\2.html)', text)

    prefix = f"{prefix}{page_info['page']}" if "page" in page_info else ""
    # Refs of the form :ref:`page`
    text = _re_simple_ref.sub(rf'[\1]({prefix}#\1)', text)
    # Refs of the form :ref:`text <page>`
    text = _re_ref_with_description.sub(rf'[\1]({prefix}#\2)', text)

    # Links with a prefix
    # TODO: when it exists, use the API to deal with prefix links properly.
    prefix = f"https://github.com/huggingface/{package_name}/tree/master/"
    text = _re_prefix_links.sub(fr'[\1]({prefix}\2)', text)
    # Other links
    text = _re_links.sub(r"[\1](\2)", text)
    return text


# Re pattern that catches examples blocks of the form `Example::`.
_re_example = re.compile("^\s*(\S.*)::\s*$")
# Re pattern that catches rst blocks of the form `.. block_name::`.
_re_block = re.compile(r"^\s*\.\.\s+(\S+)::")
# Re pattern that catches what's after the :: in rst blocks of the form `.. block_name:: something`.
_re_block_info = re.compile(r"^\s*\.\.\s+\S+::\s*(\S.*)$")


def is_empty_line(line):
    return len(line) == 0 or line.isspace()


def find_indent(line):
    """
    Returns the number of spaces that start a line indent.
    """
    search = re.search("^(\s*)(?:\S|$)", line)
    if search is None:
        return 0
    return len(search.groups()[0])


_re_rst_option = re.compile("^\s*:(\S+):(.*)$")


def convert_special_chars(text):
    """
    Converts { and < that have special meanings in MDX.
    """
    text = text.replace("{", "&amp;lcub;")
    # We don't want to replace those by the HTML code, so we temporarily set them at LTHTML
    text = re.sub(r"<(img|br|hr)", r"LTHTML\1", text) # html void elements with no closing counterpart
    _re_lt_html = re.compile(r"<(\S+)([^>]*>)(((?!</\1>).)*)<(/\1>)", re.DOTALL)
    while _re_lt_html.search(text):
        text = _re_lt_html.sub(r"LTHTML\1\2\3LTHTML\5", text)
    text = re.sub(r"(^|[^<])<([^<]|$)", r"\1&amp;lt;\2", text)
    text = text.replace("LTHTML", "<")
    return text


def parse_options(block_content):
    """
    Parses the option in some rst block content.
    """
    block_lines = block_content.split("\n")
    block_indent = find_indent(block_lines[0])
    current_option = None
    result = {}
    for line in block_lines:
        if _re_rst_option.search(line) is not None:
            current_option, value = _re_rst_option.search(line).groups()
            result[current_option] = value.lstrip()
        elif find_indent(line) > block_indent:
            result[current_option] += " " + line.lstrip()
    
    return result


def convert_rst_blocks(text):
    """
    Converts rst special blocks (examples, notes) into MDX.
    """
    lines = text.split("\n")
    idx = 0
    new_lines = []
    while idx < len(lines):
        block_type = None
        block_info = None
        if _re_block.search(lines[idx]) is not None:
            block_type = _re_block.search(lines[idx]).groups()[0]
            if _re_block_info.search(lines[idx]) is not None:
                block_info = _re_block_info.search(lines[idx]).groups()[0]
        elif _re_example.search(lines[idx]) is not None:
            block_type = "code-block"
            block_info = "python"
            example_name = _re_example.search(lines[idx]).groups()[0]
            new_lines.append(f"> {example_name}:\n")
        elif lines[idx].strip() == "..":
            block_type = "comment"
        elif lines[idx].strip() == "::":
            block_type = "code-block"
        
        if block_type is not None:
            block_indent = find_indent(lines[idx])
            # Find the next nonempty line
            idx += 1
            while idx < len(lines) and is_empty_line(lines[idx]):
                idx += 1
            # Grab the indent of the return line, this block will stop when we unindent under it (or has already)
            example_indent = find_indent(lines[idx]) if idx < len(lines) else block_indent
            
            if example_indent == block_indent:
                block_content = ""
            else:
                block_lines = []
                while idx < len(lines) and (is_empty_line(lines[idx]) or find_indent(lines[idx]) >= example_indent):
                    block_lines.append(lines[idx][example_indent:])
                    idx += 1
                block_content = "\n".join(block_lines)
            
            if block_type in ["code", "code-block"]:
                prefix = "```" if block_info is None else f"```{block_info}"
                new_lines.append(f"{prefix}\n{block_content.strip()}\n```\n")
            elif block_type == "note":
                new_lines.append(f"<Tip>\n\n{block_content.strip()}\n\n</Tip>\n")
            elif block_type == "warning":
                new_lines.append("<Tip warning={true}>\n\n" + f"{block_content.strip()}\n\n</Tip>\n")
            elif block_type == "raw":
                new_lines.append(block_content.strip() + "\n")
            elif block_type == "math":
                new_lines.append(f"$${block_content.strip()}$$\n")
            elif block_type == "comment":
                new_lines.append(f"<!--{block_content.strip()}\n-->\n")
            elif block_type == "autofunction":
                if block_info is not None:
                    new_lines.append(f"[[autodoc]] {block_info}\n")
            elif block_type == "autoclass":
                if block_info is not None:
                    block = f"[[autodoc]] {block_info}\n"
                    options = parse_options(block_content)
                    if "special-members" in options:
                        special_members = options["special-members"].split(", ")
                        for special_member in special_members:
                            block += f"    - {special_member}\n"
                    if "members" in options:
                        members = options["members"]
                        if len(members) == 0:
                            block += "    - all\n"
                        else:
                            for member in members.split(", "):
                                block += f"    - {member}\n"
                    new_lines.append(block)
            elif block_type == "image":
                options = parse_options(block_content)
                target = options.pop("target", None)
                if block_info is not None:
                    options["src"] = block_info
                else:
                    if target is None:
                        raise ValueError("Image source not defined.")
                    options["src"] = target
                html_code = " ".join([f'{key}="{value}"' for key, value in options.items()])
                new_lines.append(f"<img {html_code}/>\n")
                    
            else:
                new_lines.append(f"{block_type},{block_info}\n{block_content.rstrip()}\n")

        else:
            new_lines.append(lines[idx])
            idx += 1
    
    return "\n".join(new_lines)


# Re pattern that catches rst args blocks of the form `Parameters:`.
_re_args = re.compile("^\s*(Args?|Parameters?):\s*$")
# Re pattern that catches return blocks of the form `Return:`.
_re_returns = re.compile("^\s*Returns?:\s*$")


def split_return_line(line):
    """
    Split the return line with format `type: some doc`. Type may contain colons in the form of :obj: or :class:.
    """
    splits_on_colon = line.split(":")
    idx = 1
    while idx < len(splits_on_colon) and splits_on_colon[idx] in ["obj", "class"]:
        idx += 2
    if idx >= len(splits_on_colon):
        return None, line
    return ":".join(splits_on_colon[:idx]), ":".join(splits_on_colon[idx:])


def split_arg_line(line):
    """
    Split the return line with format `type: some doc`. Type may contain colons in the form of :obj: or :class:.
    """
    splits_on_colon = line.split(":")
    idx = 1
    while idx < len(splits_on_colon) and splits_on_colon[idx] in ["obj", "class"]:
        idx += 2
    if idx >= len(splits_on_colon):
        return line, ""
    return ":".join(splits_on_colon[:idx]), ":".join(splits_on_colon[idx:])


class InvalidRstDocstringError(ValueError): pass


def parse_rst_docstring(docstring):
    """
    Parses a docstring written in rst, in particular the list of arguments and the return type.
    """
    lines = docstring.split("\n")
    idx = 0
    while idx < len(lines):
        # Parameters section
        if _re_args.search(lines[idx]) is not None:
            # Title of the section. TODO: change this when we have the proper syntax.
            lines[idx] = "> Parameters\n"
            # Find the next nonempty line
            idx += 1
            while is_empty_line(lines[idx]):
                idx += 1
            # Grab the indent of the list of parameters, this block will stop when we unindent under it.
            param_indent = find_indent(lines[idx])
            while idx < len(lines) and find_indent(lines[idx]) == param_indent:
                intro, doc = split_arg_line(lines[idx])
                lines[idx] = re.sub(r"^\s*(\S+)(\s)", r"- **\1**\2", intro) + " --" + doc
                idx += 1
                while idx < len(lines) and (is_empty_line(lines[idx]) or find_indent(lines[idx]) > param_indent):
                    idx += 1
        
        # Returns section
        elif _re_returns.search(lines[idx]) is not None:
            # Title of the section. TODO: change this when we have the proper syntax.
            lines[idx] = "> Returns\n"
            # Find the next nonempty line
            idx += 1
            while is_empty_line(lines[idx]):
                idx += 1
            # Grab the indent of the return line, this block will stop when we unindent under it.
            return_indent = find_indent(lines[idx])
            # The line may contain the return type.
            return_type, lines[idx] = split_return_line(lines[idx])
            idx += 1
            while idx < len(lines) and (is_empty_line(lines[idx]) or find_indent(lines[idx]) >= return_indent):
                idx += 1
            
            # Return block finished, we insert the return type if one was specified
            if return_type is not None:
                # TODO: change this when we have the proper syntax
                lines[idx - 1] += f"\n> Return type\n\n{return_type}\n"
        
        else:
            idx += 1

    return "\n".join(lines)


_re_list = re.compile("^\s*(-|\*|\d+\.)\s")
_re_autodoc = re.compile("^\s*\[\[autodoc\]\]\s+(\S+)\s*$")


def remove_indent(text):
    """
    Remove indents in text, except the one linked to lists (or sublists).
    """
    lines = text.split("\n")
    # List of indents to remember for nested lists
    current_indents = []
    # List of new indents to remember for nested lists
    new_indents = []
    for idx, line in enumerate(lines):
        # Line is an item in a list.
        if _re_list.search(line) is not None:
            indent = find_indent(line)
            # Is it a new list / new level of nestedness?
            if len(current_indents) == 0 or indent > current_indents[-1]:
                current_indents.append(indent)
                new_indent = 0 if len(new_indents) == 0 else new_indents[-1]
                lines[idx] = " " * new_indent + line[indent:]
                new_indent += len(_re_list.search(line).groups()[0]) + 1
                new_indents.append(new_indent)
            # Otherwise it's an existing level of list (current one, or previous one)
            else:
                # Let's find the proper level of indentation
                level = len(current_indents) - 1
                while level >= 0 and current_indents[level] != indent:
                    level -= 1
                current_indents = current_indents[:level+1]
                new_indents = new_indents[:level]
                new_indent = 0 if len(new_indents) == 0 else new_indents[-1]
                lines[idx] = " " * new_indent + line[indent:]
                new_indent += len(_re_list.search(line).groups()[0]) + 1
                new_indents.append(new_indent)
        
        # Line is an autodoc, we keep the indent for the list just after if there is one.
        elif _re_autodoc.search(line) is not None:
            indent = find_indent(line)
            current_indents = [indent]
            new_indents = [4]
            lines[idx] = line.strip()

        # Deal with empty lines separately
        elif is_empty_line(line):
            lines[idx] = ""
        else:
            indent = find_indent(line)
            if len(current_indents) > 0 and indent > current_indents[-1]:
                lines[idx] = " " * new_indents[-1] + line[indent:]
            elif len(current_indents) > 0:
                # Let's find the proper level of indentation
                level = len(current_indents) - 1
                while level >= 0 and current_indents[level] != indent:
                    level -= 1
                current_indents = current_indents[:level+1]
                if level >= 0:
                    new_indents = new_indents[:level]
                    new_indent = 0 if len(new_indents) == 0 else new_indents[-1]
                    lines[idx] = " " * new_indent + line[indent:]
                    new_indents.append(new_indent)
                else:
                    new_indents = []
                    lines[idx] = line[indent:]
            else:
                lines[idx] = line[indent:]
                
    return "\n".join(lines)


def base_rst_to_mdx(text, page_info):
    """
    Convert a text from rst to mdx, with the base operations necessary for both docstrings and rst docs.
    """
    text = convert_rst_links(text, page_info)
    text = convert_special_chars(text)
    text = convert_rst_blocks(text)
    # Convert * in lists to - to avoid the formatting conversion treat them as bold.
    text = re.sub(r"^(\s*)\*(\s)", r"\1-\2", text, flags=re.MULTILINE)
    text = convert_rst_formatting(text)
    return remove_indent(text)


def convert_rst_docstring_to_mdx(docstring, page_info):
    """
    Convert a docstring written in rst to mdx.
    """
    text = parse_rst_docstring(docstring)
    return base_rst_to_mdx(text, page_info)


def process_titles(lines):
    """ Converts rst titles to markdown titles."""
    title_chars =  """= - ` : ' " ~ ^ _ * + # < >""".split(" ")
    title_levels = {}
    new_lines = []
    for line in lines:
        if len(new_lines) > 0 and len(line) >= len(new_lines[-1]) and len(set(line)) == 1 and line[0] in title_chars and line != "::":
            char = line[0]
            level = title_levels.get(char, len(title_levels) + 1)
            if level not in title_levels:
                title_levels[char] = level
            new_lines[-1] = f"{'#' * level} {new_lines[-1]}"
        else:
            new_lines.append(line)
    return new_lines


# Matches lines with a pattern of a table new line in rst.
_re_ignore_line_table = re.compile("^(\+[\-\s]+)+\+\s*$")
# Matches lines with a pattern of a table new line in rst, with a first column empty.
_re_ignore_line_table1 = re.compile("^\|\s+(\+[\-\s]+)+\+\s*$")
# Matches lines with a pattern of a first table line in rst.
_re_sep_line_table = re.compile("^(\+[=\s]+)+\+\s*$")
# Re pattern that catches anchors of the type .. reference:
_re_anchor_section = re.compile(r"^\.\.\s+_(\S+):")


def split_pt_tf_code_blocks(text):
    """
    Split PyTorch and TensorFlow specific block codes.
    """
    lines = text.split("\n")
    new_lines = []
    idx = 0
    while idx < len(lines):
        if lines[idx].startswith("```"):
            code_lines = {"common": [lines[idx]], "pytorch": [], "tensorflow": []}
            is_pytorch = False
            is_tensorflow = False
            idx += 1
            while idx < len(lines) and lines[idx].strip() != "```":
                if "## PYTORCH CODE" in lines[idx]:
                    is_pytorch = True
                    is_tensorflow = False
                elif "## TENSORFLOW CODE" in lines[idx]:
                    is_tensorflow = True
                    is_pytorch = False
                elif is_pytorch:
                    code_lines["pytorch"].append(lines[idx])
                elif is_tensorflow:
                    code_lines["tensorflow"].append(lines[idx])
                else:
                    code_lines["common"].append(lines[idx])
                idx += 1
            if len(code_lines["pytorch"]) > 0 or len(code_lines["tensorflow"]) > 0:
                block_lines = ["{#if fw === 'pt'}"] + code_lines["common"].copy() + code_lines["pytorch"] + ["```"]
                block_lines += ["{:else}"] + code_lines["common"].copy() + code_lines["tensorflow"] + ["```", "{/if}"]
                new_lines.extend(block_lines)
            else:
                block_lines = code_lines["common"] + ["```"]
                new_lines.extend(block_lines)
            idx += 1
        else:
            new_lines.append(lines[idx])
            idx += 1
    return "\n".join(new_lines)


def convert_rst_to_mdx(rst_text, page_info):
    """
    Convert a document written in rst to mdx.
    """
    lines = rst_text.split("\n")
    lines = process_titles(lines)
    new_lines = [
        "<script>",
        '	import Tip from "../../Tip.svelte";',
        '	import Youtube from "../../Youtube.svelte";'
        "	",
        '	export let fw: "pt" | "tf"',
        "</script>",
        "",
    ]
    for line in lines:
        if _re_ignore_line_table.search(line) is not None:
            continue
        elif _re_ignore_line_table1.search(line) is not None:
            continue
        elif _re_sep_line_table.search(line) is not None:
            line = line.replace('=', '-').replace('+', '|')
        elif _re_anchor_section.search(line) is not None:
            anchor_name = _re_anchor_section.search(line).groups()[0]
            line = f"<a id='{anchor_name}'></a>"
        new_lines.append(line)
    text = "\n".join(new_lines)

    return split_pt_tf_code_blocks(base_rst_to_mdx(text, page_info))