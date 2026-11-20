"""保护曾经在不同发布文档里发生过冲突的声明和封面规则。"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = (ROOT / 'references/platforms.md').read_text(encoding='utf-8')


class PublishingRules(unittest.TestCase):
    def test_declarations(self):
        section = TABLE.split('\n## 内容声明\n', 1)[1].split('\n## ', 1)[0]
        branches = {'小红书': ('笔记含AI合成内容', '不选'), '抖音': ('内容由AI生成', '无需添加自主声明'),
                    'B站': ('含AI生成内容', '内容无需标注'), '微信视频号': ('含AI生成内容', '无需标注')}
        for platform, labels in branches.items():
            with self.subTest(platform=platform):
                row, = (line for line in section.splitlines() if line.startswith('| ' + platform + ' |'))
                for label in labels:
                    self.assertIn(label, row)
        for path in [ROOT / 'SKILL.md', ROOT / 'README.md', *sorted((ROOT / 'references').glob('*.md'))]:
            with self.subTest(file=path.name):
                text = path.read_text(encoding='utf-8')
                self.assertNotRegex(text, r'一律「无需标注」|原创声明\s+默认不开|不要从视频内容自行推断是否勾选原创')

    def test_bilibili_category_snapshot(self):
        text = (ROOT / 'references/bilibili-categories.md').read_text(encoding='utf-8')
        categories = {}
        for line in text.splitlines():
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if not cells or not cells[0].isdigit():
                continue
            for i in range(0, len(cells), 2):
                order, name = int(cells[i]), cells[i + 1]
                self.assertNotIn(order, categories)
                categories[order] = name
        self.assertEqual(sorted(categories), list(range(1, 31)))
        self.assertEqual(len(set(categories.values())), 30)
        self.assertEqual([categories[n] for n in (1, 11, 12, 28, 30)], ['影视', '人工智能', '科技数码', 'vlog', '生活经验'])

    def test_wechat_cover_slots(self):
        section = TABLE.split('\n### 视频号封面\n', 1)[1].split('\n---', 1)[0]
        portrait, = (line for line in section.splitlines() if line.startswith('| 竖屏'))
        landscape, = (line for line in section.splitlines() if line.startswith('| 横屏'))
        self.assertRegex(portrait, r'1 个.*3:4.*共用')
        self.assertRegex(landscape, r'2 个.*个人主页卡片 3:4.*分享卡片 4:3')
        for path in [ROOT / 'SKILL.md', *sorted((ROOT / 'references').glob('*.md'))]:
            with self.subTest(file=path.name):
                text = path.read_text(encoding='utf-8')
                self.assertNotRegex(text, r'视频号[^\n]*(?:只剩单一|只剩这一个|两个都要变)|横屏封面在视频号[^\n]*没有槽可放')

    def test_xiaohongshu_orientation_cover_rule(self):
        for rel in ('SKILL.md', 'references/platforms.md', 'references/verification.md'):
            text = (ROOT / rel).read_text(encoding='utf-8')
            with self.subTest(file=rel):
                self.assertRegex(text, r'竖屏[^\n]*3:4')
                self.assertRegex(text, r'横屏[^\n]*4:3')
                self.assertNotRegex(text, r'默认\s*3:4\s*竖屏|封面默认用\s*3:4\s*竖图')


    def test_no_activity_association_rule(self):
        for rel in ('SKILL.md', 'references/platforms.md', 'references/verification.md', 'references/gotchas.md'):
            text = (ROOT / rel).read_text(encoding='utf-8')
            with self.subTest(file=rel):
                self.assertRegex(text, r'关联活动|禁止关联活动')
                self.assertIn('取消关联', text)
                self.assertNotRegex(text, r'走「参与话题\s*→\s*搜索更多话题」，精确选词并确认')


if __name__ == '__main__':
    unittest.main()
