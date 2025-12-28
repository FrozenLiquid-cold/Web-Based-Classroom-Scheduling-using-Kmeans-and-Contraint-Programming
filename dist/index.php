<?php
$index = __DIR__ . '/../dist/index.html';
if (!file_exists($index)) {
	echo 'Build not found. Run npm run build.';
	exit;
}
readfile($index);
?>

