# 이 프로젝트의 협업 수단

hiway-kit 저장소에서 별도 worker를 사용하는 감독형 협업은 Orca로 관리한다.
Claude·Codex 등 하네스에 관계없이 설치된 orchestration 가이드와 실제 런타임 계약을 따른다.
작은 작업은 부모가 직접 수행할 수 있다. 이 선택은 소비자 프로젝트에 강제하지 않는다.

공통 책임은 `plugins/common/skills/control-loop/SKILL.md`, 구체적인 경로·하네스 차이는
[운송 부록](../control-loop-transport.md)을 읽는다. 명시된 운송을 내부 subagent로
묵시적으로 대체하지 않는다. 개인 모델 선호는 전역 설정·사용자 지침에 두고 배포 규범에 넣지 않는다.
