import inspect
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass

import app.domain as domain
from app.domain import (
    CinematicLanguage,
    ColorSystem,
    CompositionPrinciples,
    ContinuityPrinciples,
    CreativeLimits,
    Identity,
    LightingPrinciples,
    PhotographyPrinciples,
    QualityCriteria,
    RealismAndAbstraction,
    SymbolicSystem,
    TextureAndMateriality,
    VisualBible,
    VisualPhilosophy,
)


VISUAL_BIBLE_MODELS = (
    VisualPhilosophy,
    Identity,
    CinematicLanguage,
    RealismAndAbstraction,
    SymbolicSystem,
    CompositionPrinciples,
    PhotographyPrinciples,
    LightingPrinciples,
    ColorSystem,
    TextureAndMateriality,
    ContinuityPrinciples,
    CreativeLimits,
    QualityCriteria,
    VisualBible,
)


class VisualBibleDomainTest(unittest.TestCase):

    def _visual_bible(self):
        philosophy = VisualPhilosophy(
            beauty="sober beauty",
            elegance="quiet elegance",
            sobriety="precise restraint",
            excess="rejected ornament",
            artifice="only when honest",
            authenticity="physical credibility",
            naturalness="unforced presence",
            non_negotiable_principles=(
                "no generic spectacle",
            ),
            incompatible_images=(
                "decorative excess without meaning",
            )
        )
        identity = Identity(
            visual_statement="contemplative cinematic clarity",
            sensibility="minimal and grounded",
            dominant_tone="quiet",
            visual_personality="restrained",
            recognition="lucid symbolic realism"
        )
        cinematic_language = CinematicLanguage(
            rhythm="slow",
            observational_distance="measured",
            immersion="calm",
            theatricality="contained",
            audiovisual_energy="low and precise"
        )
        realism = RealismAndAbstraction(
            realism_level="grounded",
            stylization_level="restrained",
            abstraction_level="symbolic but legible",
            poetic_license="controlled",
            artifice_limits=(
                "no empty surrealism",
            )
        )
        symbols = SymbolicSystem(
            allowed_symbols=(
                "reflection",
            ),
            recurring_symbols=(
                "scale echoes",
            ),
            forbidden_symbols=(
                "literal portal",
            ),
            literalness="low",
            metaphor_degree="moderate"
        )
        composition = CompositionPrinciples(
            balance="centered calm",
            negative_space="generous",
            density="low",
            scale="clear",
            hierarchy="single dominant idea",
            figure_ground_relationship="clean separation"
        )
        photography = PhotographyPrinciples(
            point_of_view="observational",
            emotional_distance="respectful",
            depth="layered",
            optical_texture="natural",
            naturalism="photographic",
            subject_relationship="quiet attention"
        )
        lighting = LightingPrinciples(
            dominant_source="motivated soft source",
            motivation="diegetic",
            contrast="gentle",
            shadow="present but readable",
            visibility="clear",
            atmosphere="subtle"
        )
        color = ColorSystem(
            dominant_temperature="warm neutral",
            base_palette=(
                "graphite",
                "soft gold",
            ),
            secondary_palettes=(
                "muted stone",
            ),
            saturation="low",
            contrast="measured",
            colors_to_avoid=(
                "neon excess",
            ),
            evolution_rules=(
                "preserve contemplative warmth",
            )
        )
        texture = TextureAndMateriality(
            preferred_materials=(
                "stone",
                "paper",
            ),
            tactility="visible",
            grain="subtle",
            detail="credible",
            polish="not plastic",
            naturalness="materially grounded"
        )
        continuity = ContinuityPrinciples(
            atmosphere="quiet",
            light="motivated",
            color="restrained",
            symbols="controlled recurrence",
            scale="macro and micro relation",
            density="low"
        )
        limits = CreativeLimits(
            foreign_styles=(
                "generic sci-fi gloss",
            ),
            cliches=(
                "glowing portal",
            ),
            excesses=(
                "decorative complexity",
            ),
            incompatible_resources=(
                "stock fantasy spectacle",
            ),
            unacceptable_artifice_levels=(
                "unmotivated surrealism",
            )
        )
        quality = QualityCriteria(
            coherence="belongs to the whole",
            elegance="quiet",
            specificity="concrete",
            naturalness="unforced",
            cinematic_strength="strong but restrained",
            generic_aesthetic_absence="no default AI look",
            belonging="consistent with philosophy"
        )

        return VisualBible(
            philosophy=philosophy,
            identity=identity,
            cinematic_language=cinematic_language,
            realism_and_abstraction=realism,
            symbolic_system=symbols,
            composition=composition,
            photography=photography,
            lighting=lighting,
            color=color,
            texture_and_materiality=texture,
            continuity=continuity,
            creative_limits=limits,
            quality=quality
        )

    def test_all_visual_bible_models_are_frozen_dataclasses(self):
        for model in VISUAL_BIBLE_MODELS:
            with self.subTest(
                model=model.__name__
            ):
                self.assertTrue(
                    is_dataclass(
                        model
                    )
                )
                self.assertTrue(
                    model.__dataclass_params__.frozen
                )

    def test_visual_bible_can_be_composed_from_approved_sections(self):
        bible = self._visual_bible()

        self.assertEqual(
            bible.philosophy.beauty,
            "sober beauty"
        )
        self.assertEqual(
            bible.identity.visual_statement,
            "contemplative cinematic clarity"
        )
        self.assertEqual(
            bible.cinematic_language.rhythm,
            "slow"
        )
        self.assertEqual(
            bible.quality.belonging,
            "consistent with philosophy"
        )

    def test_visual_bible_models_are_immutable(self):
        philosophy = VisualPhilosophy(
            beauty="sober beauty"
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            philosophy.beauty = "changed"

        bible = self._visual_bible()

        with self.assertRaises(
            FrozenInstanceError
        ):
            bible.identity = Identity()

    def test_visual_bible_is_only_an_aggregator(self):
        field_names = tuple(
            field.name
            for field in fields(
                VisualBible
            )
        )

        self.assertEqual(
            field_names,
            (
                "philosophy",
                "identity",
                "cinematic_language",
                "realism_and_abstraction",
                "symbolic_system",
                "composition",
                "photography",
                "lighting",
                "color",
                "texture_and_materiality",
                "continuity",
                "creative_limits",
                "quality",
            )
        )

    def test_visual_philosophy_owns_only_approved_concepts(self):
        self.assertEqual(
            tuple(
                field.name
                for field in fields(
                    VisualPhilosophy
                )
            ),
            (
                "beauty",
                "elegance",
                "sobriety",
                "excess",
                "artifice",
                "authenticity",
                "naturalness",
                "non_negotiable_principles",
                "incompatible_images",
            )
        )

    def test_public_domain_imports_expose_visual_bible_models(self):
        for model in VISUAL_BIBLE_MODELS:
            with self.subTest(
                model=model.__name__
            ):
                self.assertIs(
                    getattr(
                        domain,
                        model.__name__
                    ),
                    model
                )

    def test_visual_bible_domain_has_no_backend_runtime_or_prompt_terms(self):
        source = inspect.getsource(
            __import__(
                "app.domain.visual_bible",
                fromlist=[
                    "x"
                ]
            )
        )

        forbidden = (
            "ComfyUI",
            "Flux",
            "HTTP",
            "ImageBuilder",
            "ImagePromptSystem",
            "ComfyUIBackend",
            "ImageManifestWriter",
            "prompt",
            "payload",
            "workflow",
            "output_path",
            "file_path",
            "route",
            "url",
            "requests",
            "urllib",
        )

        lowered = source.lower()

        for item in forbidden:
            with self.subTest(
                item=item
            ):
                self.assertNotIn(
                    item.lower(),
                    lowered
                )

    def test_visual_bible_models_have_no_custom_public_methods(self):
        for model in VISUAL_BIBLE_MODELS:
            public_callables = [
                name
                for name, value in model.__dict__.items()
                if not name.startswith(
                    "_"
                )
                and callable(
                    value
                )
            ]

            with self.subTest(
                model=model.__name__
            ):
                self.assertEqual(
                    public_callables,
                    []
                )

    def test_visual_bible_module_does_not_import_runtime_modules(self):
        source = inspect.getsource(
            __import__(
                "app.domain.visual_bible",
                fromlist=[
                    "x"
                ]
            )
        )

        self.assertNotIn(
            "app.modules",
            source
        )
        self.assertNotIn(
            "app.managers",
            source
        )
        self.assertNotIn(
            "app.controllers",
            source
        )


if __name__ == "__main__":
    unittest.main()
