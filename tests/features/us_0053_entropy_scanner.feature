Feature: Shannon Entropy Secret Scanner Rule Plugin Engine
  As a security engineer
  I want Shannon entropy secret scanning with custom rule plugins and allowlists
  So that high-entropy credential leaks are blocked while avoiding false positives

  Scenario: Detecting high-entropy tokens exceeding custom threshold
    Given a staged source file containing an unannotated 48-character high-entropy secret token
    When the security scanner evaluates the file using Shannon entropy analysis
    Then the token is flagged as a credential leak risk
    And the security check exits with code 1

  Scenario: Respecting custom project allowlists and pragma annotations
    Given a test fixture token annotated with "# pragma: allowlist secret"
    When the security scanner runs in strict entropy mode
    Then the annotated token is safely ignored
    And the security check passes with exit code 0
