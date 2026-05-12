import pytest
from fluxmail.template import EmailTemplate


class TestEmailTemplate:
    def test_render_substitutes_variable(self):
        tmpl = EmailTemplate("Hello, {{ name }}!")
        assert tmpl.render(name="Alice") == "Hello, Alice!"

    def test_render_multiple_variables(self):
        tmpl = EmailTemplate("Dear {{ first }} {{ last }},")
        assert tmpl.render(first="John", last="Doe") == "Dear John Doe,"

    def test_render_no_variables(self):
        tmpl = EmailTemplate("No placeholders here.")
        assert tmpl.render() == "No placeholders here."

    def test_from_file_reads_template(self, tmp_path):
        f = tmp_path / "tmpl.txt"
        f.write_text("Hi {{ user }}", encoding="utf-8")
        tmpl = EmailTemplate.from_file(str(f))
        assert tmpl.render(user="Bob") == "Hi Bob"

    def test_autoescape_off_by_default(self):
        tmpl = EmailTemplate("<b>{{ value }}</b>")
        result = tmpl.render(value="<script>alert(1)</script>")
        assert "<script>" in result

    def test_autoescape_on_escapes_html(self):
        tmpl = EmailTemplate("<b>{{ value }}</b>", autoescape=True)
        result = tmpl.render(value="<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_from_file_with_autoescape(self, tmp_path):
        f = tmp_path / "tmpl.html"
        f.write_text("{{ content }}", encoding="utf-8")
        tmpl = EmailTemplate.from_file(str(f), autoescape=True)
        result = tmpl.render(content="<b>bold</b>")
        assert "&lt;b&gt;" in result

    def test_from_file_missing_raises_fluxmail_exception(self, tmp_path):
        from fluxmail import FluxMailException
        with pytest.raises(FluxMailException) as exc_info:
            EmailTemplate.from_file(str(tmp_path / "nonexistent.txt"))
        assert exc_info.value.code == "read_error"
        assert "nonexistent.txt" in str(exc_info.value)
