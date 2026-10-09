"""La prueba usa CSV ficticios de eventos, NO biometría ni resultados medidos."""
import unittest
from evaluate import episodes, metrics


class MetricsTest(unittest.TestCase):
    def test_confusion_matrix(self):
        result = metrics({'tp': 8, 'tn': 8, 'fp': 2, 'fn': 2})
        self.assertEqual(result['accuracy'], .8)
        self.assertEqual(result['fpr'], .2)
        self.assertFalse(result['target_fpr_less_than_0_2'])

    def test_short_look_not_event(self):
        rows = [{'time_ms': str(t), 'gaze_away': '1'} for t in range(0, 1200, 100)]
        self.assertEqual(episodes(rows, 'gaze_away', 3000), [])

    def test_long_look_one_event(self):
        rows = [{'time_ms': str(t), 'gaze_away': '1'} for t in range(0, 4200, 100)]
        spans = episodes(rows, 'gaze_away', 3000)
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0], (0, 4100))

    def test_person_passes_briefly_not_event(self):
        rows = [{'time_ms': str(t), 'extra_person': '1'} for t in range(0, 1000, 100)]
        self.assertFalse(episodes(rows, 'extra_person', 2000))


if __name__ == '__main__':
    unittest.main()
