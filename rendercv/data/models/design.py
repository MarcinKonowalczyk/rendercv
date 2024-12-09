"""
The `rendercv.data.models.design` module contains the data model of the `design` field
of the input file.
"""

import importlib
import importlib.util
import pathlib
import os
from typing import Annotated, Any

import pydantic

from ...themes import (
    ClassicThemeOptions,
    EngineeringresumesThemeOptions,
    ModerncvThemeOptions,
    Sb2novThemeOptions,
)
from . import entry_types

from .base import RenderCVBaseModelWithoutExtraKeys

# ======================================================================================
# Create validator functions: ==========================================================
# ======================================================================================


def validate_design_options(
    design: Any,
    available_theme_options: dict[str, type],
    available_entry_type_names: list[str],
) -> Any:
    """Chech if the design options are for a built-in theme or a custom theme. If it is
    a built-in theme, validate it with the corresponding data model. If it is a custom
    theme, check if the necessary files are provided and validate it with the custom
    theme data model, found in the `__init__.py` file of the custom theme folder.

    Args:
        design: The design options to validate.
        available_theme_options: The available theme options. The keys are the theme
            names and the values are the corresponding data models.
        available_entry_type_names: The available entry type names. These are used to
            validate if all the templates are provided in the custom theme folder.

    Returns:
        The validated design as a Pydantic data model.
    """
    from .rendercv_data_model import INPUT_FILE_DIRECTORY

    original_working_directory = pathlib.Path.cwd()

    # Change the working directory to the input file directory:

    if isinstance(design, tuple(available_theme_options.values())):
        # Then it means it is an already validated built-in theme. Return it as it is:
        return design
    if design["theme"] in available_theme_options:
        # Then it is a built-in theme, but it is not validated yet. Validate it and
        # return it:
        ThemeDataModel = available_theme_options[design["theme"]]
        return ThemeDataModel(**design)
    # It is a custom theme. Validate it:
    theme_name: str = str(design["theme"])

    # Custom theme should only contain letters and digits:
    if not theme_name.isalnum():
        message = "The custom theme name should only contain letters and digits."
        raise ValueError(
            message,
            "theme",  # this is the location of the error
            theme_name,  # this is value of the error
        )

    custom_theme_folder = INPUT_FILE_DIRECTORY / theme_name

    # Check if the custom theme folder exists:
    if not custom_theme_folder.exists():
        message = (
            (
                f"The custom theme folder `{custom_theme_folder}` does not exist."
                " It should be in the working directory as the input file."
            ),
        )
        raise ValueError(
            message,
            "",  # this is the location of the error
            theme_name,  # this is value of the error
        )

    # check if all the necessary files are provided in the custom theme folder:
    required_entry_files = [
        entry_type_name + ".j2.tex" for entry_type_name in available_entry_type_names
    ]
    required_files = [
        "SectionBeginning.j2.tex",  # section beginning template
        "SectionEnding.j2.tex",  # section ending template
        "Preamble.j2.tex",  # preamble template
        "Header.j2.tex",  # header template
        *required_entry_files,
    ]

    for file in required_files:
        file_path = custom_theme_folder / file
        if not file_path.exists():
            message = (
                f"You provided a custom theme, but the file `{file}` is not"
                f" found in the folder `{custom_theme_folder}`."
            )
            raise ValueError(
                message,
                "",  # This is the location of the error
                theme_name,  # This is value of the error
            )

    # Import __init__.py file from the custom theme folder if it exists:
    path_to_init_file = pathlib.Path(f"{theme_name}/__init__.py")

    if path_to_init_file.exists():
        spec = importlib.util.spec_from_file_location(
            "theme",
            path_to_init_file,
        )

        theme_module = importlib.util.module_from_spec(spec)  # type: ignore
        try:
            spec.loader.exec_module(theme_module)  # type: ignore
        except SyntaxError as e:
            message = (
                f"The custom theme {theme_name}'s __init__.py file has a syntax"
                " error. Please fix it."
            )
            raise ValueError(message) from e
        except ImportError as e:
            message = (
                (
                    f"The custom theme {theme_name}'s __init__.py file has an"
                    " import error. If you have copy-pasted RenderCV's built-in"
                    " themes, make sure to update the import statements (e.g.,"
                    ' "from . import" to "from rendercv.themes import").'
                ),
            )

            raise ValueError(message) from e

        ThemeDataModel = getattr(
            theme_module,
            f"{theme_name.capitalize()}ThemeOptions",  # type: ignore
        )

        # Initialize and validate the custom theme data model:
        theme_data_model = ThemeDataModel(**design)
    else:
        # Then it means there is no __init__.py file in the custom theme folder.
        # Create a dummy data model and use that instead.
        class ThemeOptionsAreNotProvided(RenderCVBaseModelWithoutExtraKeys):
            theme: str = theme_name

        theme_data_model = ThemeOptionsAreNotProvided(theme=theme_name)

    os.chdir(original_working_directory)

    return theme_data_model


# ======================================================================================
# Create custom types: =================================================================
# ======================================================================================

# Create a custom type named RenderCVBuiltinDesign:
# It is a union of all the design options and the correct design option is determined by
# the theme field, thanks to Pydantic's discriminator feature.
# See https://docs.pydantic.dev/2.7/concepts/fields/#discriminator for more information
RenderCVBuiltinDesign = Annotated[
    ClassicThemeOptions
    | ModerncvThemeOptions
    | Sb2novThemeOptions
    | EngineeringresumesThemeOptions,
    pydantic.Field(discriminator="theme"),
]

# Create a custom type named RenderCVDesign:
# RenderCV supports custom themes as well. Therefore, `Any` type is used to allow custom
# themes. However, the JSON Schema generation is skipped, otherwise, the JSON Schema
# would accept any `design` field in the YAML input file.
RenderCVDesign = Annotated[
    pydantic.json_schema.SkipJsonSchema[Any] | RenderCVBuiltinDesign,
    pydantic.BeforeValidator(
        lambda design: validate_design_options(
            design,
            available_theme_options=available_theme_options,
            available_entry_type_names=entry_types.available_entry_type_names,
        )
    ),
]


available_theme_options = {
    "classic": ClassicThemeOptions,
    "moderncv": ModerncvThemeOptions,
    "sb2nov": Sb2novThemeOptions,
    "engineeringresumes": EngineeringresumesThemeOptions,
}

available_themes = list(available_theme_options.keys())
