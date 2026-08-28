/* بند إضافي 292 — طلبك الصريح "كملها الثلاثة كاملة": خريطة الألوان
 * (بند 288) كانت مكتوبة 3 مرات بـ3 ملفات منفصلة (animal_form.html،
 * animals_bulk_purchase.html، batches/batch_form.html) — أي لون سابع
 * يُضاف لازم يتحدّث بالثلاث أماكن يدوياً، ونسيان مكان وحد يعني تناقض
 * بصري بين الشاشات. صار مكان واحد.
 *
 * الاستخدام: كل مجموعة فقاعات HTML على الشكل:
 *   <span class="colorChips">
 *     <button class="colorChip" data-color="اسم اللون"></button>...
 *   </span>
 *   <input type="hidden" class="colorInput" name="...">
 * ثم استدعاء ColorChips.init(scopeElement) — تلوّن كل فقاعة حسب
 * COLOR_HEX (أو رمادي متقطّع محايد لأي لون مخصَّص غير موجود بالخريطة،
 * بند 287)، وتربط كل فقاعة بالـinput المجاور لها بنفس المجموعة.
 * استدعاء init() أكثر من مرة على نفس العنصر آمن (idempotent) عبر علم
 * data-wired.
 */
(function (global) {
  'use strict';

  var COLOR_HEX = {
    'أبيض': '#ffffff', 'أسود': '#1a1a1a', 'أحمر': '#b3402a',
    'بني': '#8b5e34', 'رمادي': '#9ca3af',
    'مبرقش': 'conic-gradient(#ffffff 0deg 90deg, #1a1a1a 90deg 180deg, #ffffff 180deg 270deg, #1a1a1a 270deg 360deg)',
  };
  var UNKNOWN_COLOR_HEX = '#d1d5db';

  function paintChip(chip) {
    var hex = COLOR_HEX[chip.dataset.color];
    chip.style.background = hex || UNKNOWN_COLOR_HEX;
    chip.style.borderStyle = hex ? 'solid' : 'dashed';
    chip.style.borderColor = hex ? 'var(--line)' : '#9ca3af';
  }

  function wireGroup(group) {
    if (group.dataset.wired === '1') return;
    group.dataset.wired = '1';
    var input = group.parentElement.querySelector('.colorInput');
    group.querySelectorAll('.colorChip').forEach(function (chip) {
      paintChip(chip);
      chip.addEventListener('click', function () {
        group.querySelectorAll('.colorChip').forEach(function (c) { c.style.boxShadow = 'none'; });
        chip.style.boxShadow = '0 0 0 2px var(--primary)';
        if (input) input.value = chip.dataset.color;
        var hint = group.parentElement.querySelector('.colorChipHint');
        if (hint) { hint.textContent = chip.dataset.color; hint.style.color = 'var(--text)'; }
      });
    });
    if (input && input.value) {
      var selected = group.querySelector('.colorChip[data-color="' + input.value.replace(/"/g, '\\"') + '"]');
      if (selected) selected.style.boxShadow = '0 0 0 2px var(--primary)';
      var hint = group.parentElement.querySelector('.colorChipHint');
      if (hint) { hint.textContent = input.value; hint.style.color = 'var(--text)'; }
    }
  }

  function init(scope) {
    scope = scope || document;
    var groups = (scope.classList && scope.classList.contains('colorChips'))
      ? [scope]
      : Array.prototype.slice.call(scope.querySelectorAll('.colorChips'));
    groups.forEach(wireGroup);
  }

  global.ColorChips = { init: init, COLOR_HEX: COLOR_HEX, UNKNOWN_COLOR_HEX: UNKNOWN_COLOR_HEX };
})(window);
